<p align="center">
  <img src="votyper/assets/votyper.png" alt="Votyper logo" width="80">
</p>

<h1 align="center">Votyper: real-time voice typing for Linux</h1>

<p align="center">
  <b>Press a hotkey, speak, and watch your words appear in any app.</b>
</p>

**Votyper is a real-time voice typing app for Linux.** Press a hotkey, speak, and your
words are typed live into whatever text field has focus: a browser, a code editor, a
terminal, a chat window. It is speech-to-text dictation that works in every app.

- **Real-time:** words appear as you speak, and Votyper corrects them as it hears more.
- **Works anywhere:** types into any app, on both Wayland and X11.
- **Private and offline:** speech recognition runs on your computer with
  [Moonshine](https://www.moonshine.ai). Your voice never leaves the machine, and no
  internet is needed after installation.
- **Easy to see:** a system tray icon blinks while Votyper is listening, and short
  sounds mark the start and the stop.
- **Meeting mode:** a live transcript of a conversation, shown in a window and saved to a
  text file, without typing anything into your apps.
- **Your hotkey:** Ctrl+Space by default, and you can change it from the tray icon.
- **Starts at login**, so it is always ready.
- **Light on memory:** after 20 idle minutes it frees the speech model (about 500 MB), and
  wakes it up again the next time you press the hotkey.
- **Open source**, and small enough to read: plain Python, no heavy frameworks.
- English only, for now.

## Installation

Install with one command in GNU/Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/kumarasinghe/votyper/main/scripts/install.sh | bash
```

### Use it

1. Open **Votyper** from your app menu. It also starts at every login.
2. Click into any text field and press **Ctrl+Space**. You hear a sound and the tray icon
   blinks. Speak, and your words are typed as you talk.
3. Press **Ctrl+Space** again to stop.

To change the hotkey, **click the tray icon** and press **Change hotkey…**.

### Meeting mode

Use Meeting mode to follow and keep a transcript of a call or a meeting.

1. **Click the tray icon** to open the Votyper window. The buttons are in one row at the top:
   **Change hotkey…**, **Meeting mode**, **Open folder** and **Quit votyper**.
2. Press **Meeting mode**. You hear a sound and the tray icon blinks, the same as when you
   dictate. The button now says **Stop meeting**.
3. What the microphone hears appears in the text area under the buttons, one sentence per
   line. The sentence you are saying now is shown as it forms, and it is added as a new
   line when it is finished.
4. Press **Stop meeting** to end it. The text stays in the window until you start the next meeting.

While a meeting runs:

- The dictation hotkey does nothing, and **nothing is typed into your apps**. If you were
  dictating when you pressed **Meeting mode**, dictation stops first.
- Each finished sentence is saved at once, so a crash loses at most the sentence being
  spoken. You can close the window and open it again from the tray icon; the transcript is still there.
- The text is saved in `~/.votyper/meetings/<UTC start time>.txt`, for example
  `~/.votyper/meetings/20261028T143005Z.txt`. Only you can read the file.
  There is one file per meeting, with one sentence per line.
- **Open folder** shows the transcripts folder in your file manager (it works on Linux, macOS and Windows).

### Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/kumarasinghe/votyper/main/scripts/install.sh | bash -s -- --uninstall
```

## Troubleshooting

Read the log: `~/.local/state/votyper/votyper.log`

**Good to know:** the hotkey is also seen by the app you are typing in, so choose keys
that app ignores. Typing assumes a US keyboard layout and skips characters outside
plain ASCII.

## License

Votyper is open source under the [MIT License](LICENSE). The Moonshine speech model is a
separate project with its own license terms; see [moonshine.ai](https://www.moonshine.ai).
