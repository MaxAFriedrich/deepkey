# Microphone VAD Streaming

This is a modified version of the example project [from mozila here](https://github.com/mozilla/DeepSpeech-examples/tree/r0.9/mic_vad_streaming). This version is designed to allow you to dictate passages with automatic punctuation.

**_Note_** that this is alpha software designed as a proof of concept.

Stream from microphone to DeepSpeech, using VAD (voice activity detection). A fairly simple example demonstrating the DeepSpeech streaming API in Python. Also useful for quick, real-time testing of models and decoding parameters.

## Installation




Uses portaudio for microphone access, so on Linux, you may need to install its header files to compile the `pyaudio` package and you need `xdotool` to get key inject to work.

You will so need to install the `pip` packages in the `requirements.txt`.

You also needs to download scoring and the model files from mozilla.

 
You can install the entire application using the following commands.
``` bash
git clone ...
cd deepkey
sudo apt install portaudio19-dev xdotool
pip install -r requirements.txt
wget -O moz.pbmm https://github.com/mozilla/DeepSpeech/releases/download/v0.9.3/deepspeech-0.9.3-models.pbmm
wget -O moz.scorer https://github.com/mozilla/DeepSpeech/releases/download/v0.9.3/deepspeech-0.9.3-models.scorer
```

## Usage

```bash
python deepkey.py
```
