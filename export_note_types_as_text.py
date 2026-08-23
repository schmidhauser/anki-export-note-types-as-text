# Copyright (C) 2026 Andreas U. Schmidhauser
# SPDX-License-Identifier: AGPL-3.0-or-later

from datetime import date
from pathlib import Path
import re

from aqt import mw
from aqt.qt import (
    QAction,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    Qt,
    QVBoxLayout,
    qconnect,
)
from aqt.utils import showWarning, tooltip


HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


EXPORT_MENU_OBJECT_NAME = "schmidhauser_export_menu"
EXPORT_GROUP_PROPERTY = "schmidhauser_export_group"


def get_export_menu() -> QMenu:
    menu_bar = mw.menuBar()

    existing_menu = menu_bar.findChild(QMenu, EXPORT_MENU_OBJECT_NAME)
    if existing_menu is not None:
        return existing_menu

    export_menu = QMenu("Export", menu_bar)
    export_menu.setObjectName(EXPORT_MENU_OBJECT_NAME)
    menu_bar.insertMenu(mw.form.menuHelp.menuAction(), export_menu)

    return export_menu


def add_export_action_group(
    group_name: str,
    copy_action: QAction,
    save_action: QAction,
) -> None:
    export_menu = get_export_menu()

    copy_action.setProperty(EXPORT_GROUP_PROPERTY, group_name)
    save_action.setProperty(EXPORT_GROUP_PROPERTY, group_name)

    sort_key = group_name.casefold()

    before_action = next(
        (
            action
            for action in export_menu.actions()
            if isinstance(
                existing_group := action.property(EXPORT_GROUP_PROPERTY),
                str,
            )
            and existing_group.casefold() > sort_key
        ),
        None,
    )

    if before_action is None:
        if export_menu.actions():
            export_menu.addSeparator()

        export_menu.addAction(copy_action)
        export_menu.addAction(save_action)
    else:
        export_menu.insertAction(before_action, copy_action)
        export_menu.insertAction(before_action, save_action)
        export_menu.insertSeparator(before_action)


class NoteTypeSelectionDialog(QDialog):
    def __init__(
        self,
        note_types: list[dict],
        default_unselected: set[str],
    ) -> None:
        super().__init__(mw)

        self.setWindowTitle("Export Note Types")
        self.resize(480, 520)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Select the note types to export:", self))

        self.note_type_list = QListWidget(self)
        layout.addWidget(self.note_type_list)

        for note_type in note_types:
            name = str(note_type.get("name", ""))
            item = QListWidgetItem(name, self.note_type_list)
            item.setCheckState(
                Qt.CheckState.Unchecked
                if name in default_unselected
                else Qt.CheckState.Checked
            )

        selection_buttons = QHBoxLayout()

        select_all_button = QPushButton("Select All", self)
        select_none_button = QPushButton("Select None", self)

        qconnect(select_all_button.clicked, self._select_all)
        qconnect(select_none_button.clicked, self._select_none)

        selection_buttons.addWidget(select_all_button)
        selection_buttons.addWidget(select_none_button)
        selection_buttons.addStretch()

        layout.addLayout(selection_buttons)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )

        qconnect(self.button_box.accepted, self.accept)
        qconnect(self.button_box.rejected, self.reject)
        qconnect(self.note_type_list.itemChanged, self._update_ok_button)

        layout.addWidget(self.button_box)

        self._update_ok_button()

    def _set_all(self, state: Qt.CheckState) -> None:
        for index in range(self.note_type_list.count()):
            item = self.note_type_list.item(index)
            if item is not None:
                item.setCheckState(state)

    def _select_all(self) -> None:
        self._set_all(Qt.CheckState.Checked)

    def _select_none(self) -> None:
        self._set_all(Qt.CheckState.Unchecked)

    def _update_ok_button(
        self,
        _item: QListWidgetItem | None = None,
    ) -> None:
        ok_button = self.button_box.button(
            QDialogButtonBox.StandardButton.Ok
        )
        if ok_button is not None:
            ok_button.setEnabled(bool(self.selected_names()))

    def selected_names(self) -> list[str]:
        names: list[str] = []

        for index in range(self.note_type_list.count()):
            item = self.note_type_list.item(index)
            if (
                item is not None
                and item.checkState() == Qt.CheckState.Checked
            ):
                names.append(item.text())

        return names


def get_note_types() -> list[dict] | None:
    if mw.col is None:
        showWarning("No collection is open.", parent=mw)
        return None

    note_types = [
        note_type
        for note_type in mw.col.models.all()
        if note_type is not None
    ]

    note_types.sort(
        key=lambda note_type: (
            str(note_type.get("name", "")).casefold(),
            str(note_type.get("name", "")),
        )
    )

    if not note_types:
        tooltip("The collection contains no note types.", parent=mw)
        return None

    return note_types


def default_unselected_note_types() -> set[str]:
    config = mw.addonManager.getConfig(__name__) or {}
    value = config.get("default_unselected_note_types", [])

    if not isinstance(value, list):
        return set()

    return {
        name
        for name in value
        if isinstance(name, str)
    }


def select_note_types(
    note_types: list[dict],
) -> list[dict] | None:
    dialog = NoteTypeSelectionDialog(
        note_types,
        default_unselected_note_types(),
    )

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None

    selected_names = set(dialog.selected_names())

    return [
        note_type
        for note_type in note_types
        if note_type.get("name") in selected_names
    ]


def strip_html_comments(template: str) -> str:
    return HTML_COMMENT_RE.sub("", template)


def fenced_block(language: str, text: str) -> str:
    separator = "" if text.endswith("\n") else "\n"
    return f"````{language}\n{text}{separator}````"


def field_names(note_type: dict) -> list[str]:
    names: list[str] = []

    for index, field in enumerate(note_type.get("flds", [])):
        if isinstance(field, dict):
            names.append(str(field.get("name", f"Field {index}")))
        else:
            names.append(f"Field {index}")

    return names


def template_records(note_type: dict) -> list[tuple[int, dict]]:
    records: list[tuple[int, dict]] = []

    for index, template in enumerate(note_type.get("tmpls", [])):
        if not isinstance(template, dict):
            continue

        ordinal = template.get("ord")
        if not isinstance(ordinal, int):
            ordinal = index

        records.append((ordinal, template))

    records.sort(key=lambda record: record[0])
    return records


def format_field_list(
    ordinals: object,
    fields: list[str],
) -> str:
    if not isinstance(ordinals, (list, tuple)):
        return ""

    names: list[str] = []

    for ordinal in ordinals:
        if isinstance(ordinal, int) and 0 <= ordinal < len(fields):
            names.append(f"`{fields[ordinal]}`")
        elif isinstance(ordinal, int):
            names.append(f"`field {ordinal}`")

    return ", ".join(names)


def format_card_requirements(note_type: dict) -> list[str]:
    requirements = note_type.get("req", [])
    fields = field_names(note_type)
    templates = {
        ordinal: template
        for ordinal, template in template_records(note_type)
    }

    if not isinstance(requirements, (list, tuple)) or not requirements:
        return ["- No card-generation requirements recorded."]

    lines: list[str] = []

    for requirement in requirements:
        if (
            not isinstance(requirement, (list, tuple))
            or len(requirement) != 3
        ):
            lines.append(
                "- A card-generation requirement could not be interpreted."
            )
            continue

        card_ordinal, requirement_kind, field_ordinals = requirement

        if not isinstance(card_ordinal, int):
            lines.append(
                "- A card-generation requirement could not be interpreted."
            )
            continue

        card_number = card_ordinal + 1
        template = templates.get(card_ordinal)
        template_name = (
            str(template.get("name", ""))
            if template is not None
            else ""
        )

        card_label = f"Card {card_number}"
        if template_name:
            card_label += f" (`{template_name}`)"

        formatted_fields = format_field_list(field_ordinals, fields)

        if requirement_kind == "any":
            if formatted_fields:
                lines.append(
                    f"- {card_label} requires any non-empty field among: "
                    f"{formatted_fields}"
                )
            else:
                lines.append(
                    f"- {card_label} has an empty `any` field requirement."
                )
        elif requirement_kind == "all":
            if formatted_fields:
                lines.append(
                    f"- {card_label} requires all of: {formatted_fields}"
                )
            else:
                lines.append(
                    f"- {card_label} has an empty `all` field requirement."
                )
        elif requirement_kind == "none":
            lines.append(
                f"- {card_label} has no non-empty-field requirement."
            )
        else:
            lines.append(
                f"- {card_label} has an unrecognized "
                "card-generation requirement."
            )

    return lines


def format_note_type(note_type: dict) -> str:
    name = str(note_type.get("name", ""))
    fields = field_names(note_type)

    kind_value = note_type.get("type")
    if kind_value == 0:
        kind = "standard"
    elif kind_value == 1:
        kind = "cloze"
    else:
        kind = "unknown"

    sort_field_ordinal = note_type.get("sortf")
    if (
        isinstance(sort_field_ordinal, int)
        and 0 <= sort_field_ordinal < len(fields)
    ):
        sort_field = f"`{fields[sort_field_ordinal]}`"
    else:
        sort_field = "unknown"

    lines = [
        f"## {name}",
        "",
        f"- kind: {kind}",
        f"- sort field: {sort_field}",
        "",
        "### Fields",
        "",
    ]

    for ordinal, field_name in enumerate(fields, start=1):
        lines.append(f"{ordinal}. `{field_name}`")

    lines.extend(
        [
            "",
            "### Card-generation requirements",
            "",
            *format_card_requirements(note_type),
            "",
            "### Card types",
        ]
    )

    for ordinal, template in template_records(note_type):
        card_number = ordinal + 1
        template_name = str(template.get("name", ""))

        lines.extend(
            [
                "",
                f"#### Card {card_number}: {template_name}",
                "",
                "Front template:",
                "",
                fenced_block(
                    "html",
                    strip_html_comments(str(template.get("qfmt", ""))),
                ),
                "",
                "Back template:",
                "",
                fenced_block(
                    "html",
                    strip_html_comments(str(template.get("afmt", ""))),
                ),
            ]
        )

    return "\n".join(lines)


def format_note_types(note_types: list[dict]) -> str:
    names = [
        f"`{str(note_type.get('name', ''))}`"
        for note_type in note_types
    ]
    summary = (
        f"Exported note types ({len(note_types)}): "
        + ", ".join(names)
        + "."
    )

    sections = ["# ANKI NOTE TYPES", summary]

    for note_type in note_types:
        sections.append(format_note_type(note_type))

    return "\n\n".join(sections) + "\n"


def prepare_note_types() -> tuple[str, int] | None:
    note_types = get_note_types()

    if note_types is None:
        return None

    selected = select_note_types(note_types)

    if selected is None:
        return None

    return format_note_types(selected), len(selected)


def result_message(verb: str, total: int) -> str:
    note_type_word = "note type" if total == 1 else "note types"
    return f"{verb} {total} {note_type_word}."


def on_copy() -> None:
    prepared = prepare_note_types()

    if prepared is None:
        return

    text, total = prepared

    clipboard = QApplication.clipboard()
    if clipboard is None:
        showWarning("Could not access the clipboard.", parent=mw)
        return

    clipboard.setText(text)

    tooltip(
        result_message("Copied", total),
        parent=mw,
    )


def on_save() -> None:
    prepared = prepare_note_types()

    if prepared is None:
        return

    text, total = prepared

    default_filename = (
        f"anki-note-types-{date.today().isoformat()}.txt"
    )
    default_path = Path.home() / default_filename

    filename, _selected_filter = QFileDialog.getSaveFileName(
        mw,
        "Save Note Types as Text",
        str(default_path),
        "Text Files (*.txt)",
    )

    if not filename:
        return

    path = Path(filename)

    if not path.suffix:
        path = path.with_suffix(".txt")

    try:
        path.write_bytes(text.encode("utf-8"))
    except OSError as error:
        showWarning(
            f"Could not save the file:\n{error}",
            parent=mw,
        )
        return

    tooltip(
        result_message("Saved", total),
        parent=mw,
    )


def apply_shortcuts(config: dict) -> None:
    shortcut_copy = config.get("shortcut_copy", "")
    shortcut_save = config.get("shortcut_save", "")

    copy_action.setShortcut(
        shortcut_copy if isinstance(shortcut_copy, str) else ""
    )
    save_action.setShortcut(
        shortcut_save if isinstance(shortcut_save, str) else ""
    )


copy_action = QAction("Copy Note Types as Text…", mw)
save_action = QAction("Save Note Types as Text…", mw)

qconnect(copy_action.triggered, on_copy)
qconnect(save_action.triggered, on_save)

config = mw.addonManager.getConfig(__name__) or {}
apply_shortcuts(config)

mw.addonManager.setConfigUpdatedAction(__name__, apply_shortcuts)

add_export_action_group(
    "Note Types",
    copy_action,
    save_action,
)
