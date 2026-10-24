# desk-voice

Phone page that sends a voice message, a siren, or a knock to a Windows computer. The sound plays on that computer’s speakers.

Suggested repository name: **desk-voice**.

Nothing here is tied to one machine. Copy `.env.example` to `.env` and set the values for the computer that will play the sound.

## Settings

| Name | Default | What to set |
| --- | --- | --- |
| `HOST` | `127.0.0.1` | Leave this. The program listens only on that computer. |
| `PORT` | `8787` | Local port. Use this same number with Tailscale Serve. |
| `MAX_BYTES` | `8388608` | Largest voice upload, in bytes. `8388608` is 8 MB. |
| `MAX_SECONDS` | `60` | Longest recording. The page sends it when the time is reached. |

`.env` stays on the computer that runs the program. Do not commit it or paste it into a chat. Share `.env.example` instead.

## Run it

Requirements: Windows, Python 3, and Tailscale.

1. Copy this folder to the computer that should play the sound.
2. Copy `.env.example` to `.env`.
3. Start the receiver from that folder:

```bat
py -3 server.py
```

Or double-click `start-hidden.vbs`. That script uses the Python launcher on that computer. It does not contain a user name or a folder path.

4. Publish it on that computer’s own Tailscale name. Replace `8787` if you changed `PORT`:

```bat
tailscale serve --bg 8787
```

5. See the address for that computer:

```bat
tailscale serve status
```

The address looks like `https://<computer-name>.<tailnet>.ts.net`. It is different on every computer. Open the name that command prints.

Stop a hidden receiver by running `stop.bat` in the project folder. Closing the editor does not stop it. Restarting Windows does.

## Use it from a phone or another computer

The other device does not run Python. It opens the page.

1. Install Tailscale and sign in to the same tailnet as the computer that is playing the sound.
2. Leave that computer on, awake, and running the receiver.
3. Open the `https://` address from `tailscale serve status`.
4. Allow the microphone to send a voice message.

The microphone works on that `https://` address. A plain `http://` address on the local network will not record.

On an iPhone, use Safari. Then Share, **Add to Home Screen**, if you want an icon. The microphone stops when you leave the page. Siren and Knock do not need the microphone.

Sound plays on the computer running `server.py`, not on the phone or the other computer that opened the page.

## Page actions

| Control | What the receiver computer does |
| --- | --- |
| Microphone | Plays the voice message sent from the phone. |
| Siren | Plays a short two-tone siren. |
| Knock | Plays two knocks. |
