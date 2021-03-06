import time
import logging
from datetime import datetime
import threading
import collections
import queue
import os
import os.path
import deepspeech
import numpy as np
import pyaudio
import wave
import webrtcvad
from halo import Halo
from scipy import signal
from rpunct import RestorePuncts


logging.basicConfig(level=20)
rpunct = RestorePuncts()


class Audio(object):
    """Streams raw audio from microphone. Data is received in a separate thread, and stored in a buffer, to be read from."""

    FORMAT = pyaudio.paInt16
    # Network/VAD rate-space
    RATE_PROCESS = 16000
    CHANNELS = 1
    BLOCKS_PER_SECOND = 50

    def __init__(self, callback=None, device=None, input_rate=RATE_PROCESS, file=None):
        def proxy_callback(in_data, frame_count, time_info, status):
            #pylint: disable=unused-argument
            if self.chunk is not None:
                in_data = self.wf.readframes(self.chunk)
            callback(in_data)
            return (None, pyaudio.paContinue)
        if callback is None:
            def callback(in_data): return self.buffer_queue.put(in_data)
        self.buffer_queue = queue.Queue()
        self.device = device
        self.input_rate = input_rate
        self.sample_rate = self.RATE_PROCESS
        self.block_size = int(self.RATE_PROCESS /
                              float(self.BLOCKS_PER_SECOND))
        self.block_size_input = int(
            self.input_rate / float(self.BLOCKS_PER_SECOND))
        self.pa = pyaudio.PyAudio()

        kwargs = {
            'format': self.FORMAT,
            'channels': self.CHANNELS,
            'rate': self.input_rate,
            'input': True,
            'frames_per_buffer': self.block_size_input,
            'stream_callback': proxy_callback,
        }

        self.chunk = None
        # if not default device
        if self.device:
            kwargs['input_device_index'] = self.device
        elif file is not None:
            self.chunk = 320
            self.wf = wave.open(file, 'rb')

        self.stream = self.pa.open(**kwargs)
        self.stream.start_stream()

    def resample(self, data, input_rate):
        """
        Microphone may not support our native processing sampling rate, so
        resample from input_rate to RATE_PROCESS here for webrtcvad and
        deepspeech

        Args:
            data (binary): Input audio stream
            input_rate (int): Input audio rate to resample from
        """
        data16 = np.fromstring(string=data, dtype=np.int16)
        resample_size = int(len(data16) / self.input_rate * self.RATE_PROCESS)
        resample = signal.resample(data16, resample_size)
        resample16 = np.array(resample, dtype=np.int16)
        return resample16.tostring()

    def read_resampled(self):
        """Return a block of audio data resampled to 16000hz, blocking if necessary."""
        return self.resample(data=self.buffer_queue.get(),
                             input_rate=self.input_rate)

    def read(self):
        """Return a block of audio data, blocking if necessary."""
        return self.buffer_queue.get()

    def destroy(self):
        self.stream.stop_stream()
        self.stream.close()
        self.pa.terminate()

    frame_duration_ms = property(
        lambda self: 1000 * self.block_size // self.sample_rate)

    def write_wav(self, filename, data):
        logging.info("write wav %s", filename)
        wf = wave.open(filename, 'wb')
        wf.setnchannels(self.CHANNELS)
        # wf.setsampwidth(self.pa.get_sample_size(FORMAT))
        assert self.FORMAT == pyaudio.paInt16
        wf.setsampwidth(2)
        wf.setframerate(self.sample_rate)
        wf.writeframes(data)
        wf.close()


class VADAudio(Audio):
    """Filter & segment audio with voice activity detection."""

    def __init__(self, device=None, input_rate=None):
        super().__init__(device=device, input_rate=input_rate)
        self.vad = webrtcvad.Vad(0)

    def frame_generator(self):
        """Generator that yields all audio frames from microphone."""
        if self.input_rate == self.RATE_PROCESS:
            while True:
                yield self.read()
        else:
            while True:
                yield self.read_resampled()

    def vad_collector(self, padding_ms, ratio, frames=None):
        """Generator that yields series of consecutive audio frames comprising each utterence, separated by yielding a single None.
            Determines voice activity by ratio of frames in padding_ms. Uses a buffer to include padding_ms prior to being triggered.
            Example: (frame, ..., frame, None, frame, ..., frame, None, ...)
                      |---utterence---|        |---utterence---|
        """
        if frames is None:
            frames = self.frame_generator()
        num_padding_frames = padding_ms // self.frame_duration_ms
        ring_buffer = collections.deque(maxlen=num_padding_frames)
        triggered = False

        for frame in frames:
            # if len(frame) < 640:
            #     return

            is_speech = self.vad.is_speech(frame, self.sample_rate)
            yield frame
            ring_buffer.append((frame, is_speech))
            num_unvoiced = len(
                [f for f, speech in ring_buffer if not speech])
            if num_unvoiced > ratio * ring_buffer.maxlen:
                triggered = False
                yield None
                ring_buffer.clear()


# key writer and converter
textBuffer = ""


def keyWriter(text):
    """Write the input via key strokes to the screen

    Args:
        text (string): text to write
    """
    from pyKey import sendSequence
    global textBuffer

    wordCount = len(text.split())

    if wordCount > 2:
        textBuffer = textBuffer.split(".")[-1]
        oldText = textBuffer
        textBuffer += " "+rpunct.punctuate(text, lang='en')
        text = textBuffer.replace(oldText, "")

    sendSequence(text)


def main(SETTINGS):
    # Load DeepSpeech model
    print('Initializing model...')
    logging.info("model: %s", SETTINGS["model"])
    model = deepspeech.Model(SETTINGS["model"])
    if SETTINGS["scorer"]:
        logging.info("scorer: %s", SETTINGS["scorer"])
        model.enableExternalScorer(SETTINGS["scorer"])

    # Start audio with VAD
    vad_audio = VADAudio(device=SETTINGS["device"],
                         input_rate=SETTINGS["rate"])
    print("Listening (ctrl-C to exit)...")
    frames = vad_audio.vad_collector(SETTINGS["padding"], SETTINGS["ratio"])

    # Stream from microphone to DeepSpeech using VAD
    stream_context = model.createStream()
    wav_data = bytearray()
    for frame in frames:
        if frame is not None:
            logging.debug("streaming frame")
            stream_context.feedAudioContent(np.frombuffer(frame, np.int16))
        else:
            logging.debug("end utterence")
            text = stream_context.finishStream()
            if text != "":
                print("Recognized: %s" % text)
                keyWriter(text)
            stream_context = model.createStream()


if __name__ == '__main__':
    from yaml import load
    try:
        with open("settings.yml", "r") as file:
            SETTINGS = load(file.read())
            if len(SETTINGS) != 6:
                SETTINGS = {
                    "model": "./moz.pbmm",
                    "scorer": "./moz.scorer",
                    "device": 6,
                    "rate": 16000,
                    "padding": 3000,
                    "ratio": 0.5
                }
                logging.error(
                    "Incorrect settings fromating, reverting to defaults.")
            else:
                logging.info("Loaded settings from file.")
    except:
        SETTINGS = {
            "model": "./moz.pbmm",
            "scorer": "./moz.scorer",
            "device": 6,
            "rate": 16000,
            "padding": 3000,
            "ratio": 0.5
        }
        logging.error("Incorrect settings fromating, reverting to defaults.")
    main(SETTINGS)
