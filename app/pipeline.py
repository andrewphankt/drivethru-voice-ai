"""pipeline.py — B4 voice pipeline (Pipecat 1.3, development runner).

  browser mic --WebRTC--> Whisper STT --> OrderProcessor(your model + DB)
                                              --> Kokoro TTS --WebRTC--> speaker

Structured for Pipecat's development runner: you define `bot(runner_args)`, the
runner creates the connected WebRTC transport and serves the browser client. The
OrderProcessor IS the brain — it runs VoiceOrderBrain (your `drivethru` model +
the DB) and speaks back only the <say> text; the <order> diff updates the DB.

Run:  python3 app/pipeline.py
Then open  http://localhost:7860/client  and allow the microphone.
Requires `ollama serve` running with the `drivethru` model.

⚠️ Order logic is tested; the audio classes are version-sensitive. If a service
constructor errors (e.g. WhisperSTTService/KokoroTTSService args), paste it to
Claude Code — usually a one-line fix.
"""

import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
from order_voice import VoiceOrderBrain  # noqa: E402  (tested order logic)

from pipecat.frames.frames import Frame, TranscriptionFrame, TextFrame, TTSSpeakFrame, TTSAudioRawFrame
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.pipeline.runner import PipelineRunner
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.processors.audio.vad_processor import VADProcessor
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.services.whisper.stt import WhisperSTTServiceMLX, MLXModel
from pipecat.services.kokoro.tts import KokoroTTSService


class OrderProcessor(FrameProcessor):
    """On a final transcription, run the model + DB off-thread (so audio doesn't
    stall) and emit the spoken reply as a TextFrame for TTS."""

    def __init__(self, brain: VoiceOrderBrain):
        super().__init__()
        self.brain = brain

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, TranscriptionFrame) and frame.text.strip():
            say, snap, escalated = await asyncio.to_thread(self.brain.handle, frame.text)
            print(f"CUSTOMER: {frame.text}")
            print(f"  SPEAK: {say}")
            print(f"  ORDER: {[(l['line'], l['qty'], l['item'], l['size']) for l in snap['lines']]}  [{snap['state']}]")
            if escalated:
                print("  🔔 TEAM MEMBER NEEDED — escalating to a human.", flush=True)
            # TTSSpeakFrame = "speak this now" (a bare TextFrame just gets buffered).
            await self.push_frame(TTSSpeakFrame(say))
        else:
            await self.push_frame(frame, direction)


class LatencyMeter(FrameProcessor):
    """B5: measure stop-speaking -> first-audio-out — the reply latency that
    matters (§9). Total perceived latency = this + the endpointing wait (stop_secs)."""

    def __init__(self):
        super().__init__()
        self._t_stop = None

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        name = type(frame).__name__
        if "StoppedSpeaking" in name:                 # user finished talking
            self._t_stop = time.monotonic()
        elif isinstance(frame, TTSAudioRawFrame) and self._t_stop is not None:
            ms = (time.monotonic() - self._t_stop) * 1000.0
            print(f"⏱  reply latency (stop→first-audio): {ms:.0f} ms", flush=True)
            self._t_stop = None
        await self.push_frame(frame, direction)


async def run_bot(transport):
    brain = VoiceOrderBrain()
    # Warm the model now so the FIRST real turn isn't a multi-second cold start
    # (loads `drivethru` into Ollama's memory instead of on the customer's first line).
    await asyncio.to_thread(brain.handle, "warmup")
    brain.reset()

    # VAD runs as a pipeline processor in 1.3 (VADProcessor). stop_secs is the
    # endpointing wait — how long of a quiet dip ends your turn. 0.4 was too eager:
    # a drawn-out word ("let meee...") dips in energy mid-word, looks like a 400ms
    # gap, and gets cut off. 0.8 lets drawls/pauses ride. The REAL fix is SmartTurn
    # semantic endpointing (fires on completeness, not silence) — next step (B5).
    vad = SileroVADAnalyzer(params=VADParams(
        confidence=0.4, start_secs=0.15, stop_secs=0.8, min_volume=0.0,
    ))
    # MLX Whisper: Apple-native, far faster than CPU Whisper AND more accurate
    # (fixes 'to'/'two'/'2' mishearing). First run downloads the model (~1GB).
    stt = WhisperSTTServiceMLX(model=MLXModel.LARGE_V3_TURBO_Q4)
    tts = KokoroTTSService(voice_id="af_heart")   # local; voice REQUIRED (default is None)

    pipeline = Pipeline([
        transport.input(),
        VADProcessor(vad_analyzer=vad),
        stt,
        OrderProcessor(brain),
        tts,
        LatencyMeter(),                     # B5: prints reply latency in ms
        transport.output(),
    ])
    task = PipelineTask(pipeline, params=PipelineParams(allow_interruptions=True))
    await PipelineRunner().run(task)


async def bot(runner_args):
    """Entry point the Pipecat runner calls. It hands us a connected WebRTC peer."""
    transport = SmallWebRTCTransport(
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            # NOTE: SmallWebRTC in 1.3 does NOT run VAD from here — VADProcessor
            # in the pipeline (run_bot) does. Passing vad_analyzer here is ignored.
        ),
        webrtc_connection=runner_args.webrtc_connection,
    )
    await run_bot(transport)


if __name__ == "__main__":
    from pipecat.runner.run import main
    main()
