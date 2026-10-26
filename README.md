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
- **Your hotkey:** Ctrl+Space by default, and you can change it from the tray icon.
- **Starts at login**, so it is always ready.
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

### Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/kumarasinghe/votyper/main/scripts/install.sh | bash -s -- --uninstall
```

## Troubleshooting

Read the log: `~/.local/state/votyper/votyper.log`

**Good to know:** the hotkey is also seen by the app you are typing in, so choose keys
that app ignores. Typing assumes a US keyboard layout and skips characters outside
plain ASCII.
