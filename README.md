# DISCLAIMER
At the current version, this is a proof of concept rather than an actual fix.
I wanted to know if it would work first, so I was aided by AI. If you don't like the sound of that, wait until I actually start working more seriously on this project.

# Server setup (On Windows)
Python (3.8 minimum) is required.

You'll also need to [download ffmpeg essentials from here](https://www.gyan.dev/ffmpeg/builds/).
Then, extract the folder wherever you want (The root of C:, for example) and register the "bin" folder on the PATH system environment variable.

Finally, clone or download the project, open a terminal at ".\tuberepair" and input:
```bash
python -m venv tuberepair
.\tuberepair\Scripts\Activate.ps1
pip install -r requirements.txt

# Run server
python main.py
```

# On iOS
If you're using TubeReplacer:
- Open TubeReplacer's settings panel in Settings.
- Change "Video Stream" to "Custom".
- Set the "Custom Stream URL" to the URL the console tells you the server opened at and add __/getvideo/%v__ at the end (Ex. http://192.168.1.120/getvideo/%v)

# Extra notes
- The server downloads the videos to convert them first, so long videos will take a while to load.
- The cache gets cleared at closing the server (With CTRL+C).
- For now, I won't be making a Docker option. I'm not familiar with it yet and I prefer to get the project working properly first.
- The stream is always 720p. But depending on the video, it may be 30 or 60 fps.