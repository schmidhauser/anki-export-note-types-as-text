<style>
code {
    color: #d63384;
}
</style>

### Note-Type Selection Defaults

`default_unselected_note_types` specifies the note types that are initially unselected in the **Export Note Types** dialog.

Each entry must be the exact name of a note type. Unselected note types remain available and can be selected for an individual export. An example: 

    "default_unselected_note_types": [
      "Basic",
      "Cloze"
    ]

initially unselects the note types **Basic** and **Cloze**.

Set it to the empty list (`[]`) to select all note types by default.

### Keyboard Shortcuts

`shortcut_copy` specifies the keyboard shortcut for **Copy Note Types as Text…** It is disabled by default.

`shortcut_save` specifies the keyboard shortcut for **Save Note Types as Text…** The default is `Meta+Ctrl+Shift+N` (`⌃⇧⌘N`); set it to `""` to disable it.

On macOS, Qt interprets `Meta` as Control (`⌃`), `Ctrl` as Command (`⌘`), `Alt` as Option (`⌥`), and `Shift` as Shift (`⇧`).

No restart is required.
