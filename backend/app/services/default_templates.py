"""Default rugby union (15s) and sevens tag templates, from the tag list in the spec.

Button hotkeys are lower-case letters and digits; descriptor option hotkeys are upper-case
letters (Shift + key) so that both sets fit alongside the player's own keys.
"""

from __future__ import annotations

from typing import Literal

from app.schemas.templates import (
    DescriptorGroup,
    DescriptorOption,
    TemplateButton,
    TemplateContent,
)


def _opts(*pairs: tuple[str, str | None]) -> list[DescriptorOption]:
    return [DescriptorOption(value=value, hotkey=hotkey) for value, hotkey in pairs]


def _groups() -> list[DescriptorGroup]:
    return [
        DescriptorGroup(key="outcome", label="Outcome", options=_opts(("Won", "A"), ("Lost", "S"))),
        DescriptorGroup(
            key="zone",
            label="Zone",
            options=_opts(("Own 22", "Q"), ("Own half", "W"), ("Opp half", "E"), ("Opp 22", "R")),
        ),
        DescriptorGroup(key="team", label="Team", options=_opts(("Us", "U"), ("Them", "T"))),
        DescriptorGroup(
            key="phase",
            label="Phase",
            options=_opts(("1", None), ("2", None), ("3", None), ("4+", None)),
        ),
        DescriptorGroup(
            key="tackle",
            label="Tackle",
            options=_opts(("Made", "D"), ("Missed", "G"), ("Dominant", "H")),
        ),
        DescriptorGroup(
            key="turnover", label="Turnover", options=_opts(("Won", "N"), ("Conceded", "B"))
        ),
        DescriptorGroup(
            key="kick_type",
            label="Kick",
            options=_opts(
                ("Box", "Z"), ("Grubber", "X"), ("Touch", "C"), ("Contestable", "V"), ("Goal", "O")
            ),
        ),
        DescriptorGroup(
            key="infringement",
            label="Infringement",
            options=_opts(
                ("Offside", None),
                ("Not releasing", None),
                ("Not rolling away", None),
                ("High tackle", None),
                ("Scrum", None),
                ("Lineout", None),
                ("Foul play", None),
                ("Other", None),
            ),
        ),
        DescriptorGroup(key="players", label="Players", kind="players", multiple=True),
    ]


def _button(
    code: str,
    hotkey: str,
    colour: str,
    *,
    kind: Literal["instant", "span"] = "instant",
    lead: int = 3000,
    lag: int = 3000,
    groups: tuple[str, ...] = (),
) -> TemplateButton:
    return TemplateButton(
        code=code,
        hotkey=hotkey,
        colour=colour,
        kind=kind,
        lead_ms=lead,
        lag_ms=lag,
        groups=list(groups),
    )


def fifteens_template() -> TemplateContent:
    return TemplateContent(
        name="Rugby union 15s",
        descriptor_groups=_groups(),
        outcome_group="outcome",
        success_values=["Won"],
        buttons=[
            _button("Kickoff", "1", "#1971c2", lead=2000, lag=10000, groups=("team", "zone")),
            _button("Scrum", "2", "#e8590c", kind="span", groups=("outcome", "team", "zone")),
            _button("Lineout", "3", "#f08c00", kind="span", groups=("outcome", "team", "zone")),
            _button("Maul", "4", "#9c36b5", kind="span", groups=("outcome", "team", "zone")),
            _button(
                "Ruck",
                "5",
                "#2f9e44",
                lead=2000,
                lag=4000,
                groups=("outcome", "team", "zone", "phase"),
            ),
            _button("Possession", "6", "#868e96", kind="span", groups=("team", "zone")),
            _button("Carry", "c", "#0ca678", groups=("players", "zone", "phase")),
            _button("Line break", "b", "#e03131", lead=3000, lag=6000, groups=("players", "zone")),
            _button("Tackle", "t", "#5c7cfa", groups=("tackle", "players", "zone")),
            _button(
                "Turnover", "o", "#c2255c", lead=4000, lag=4000, groups=("turnover", "team", "zone")
            ),
            _button(
                "Kick",
                "x",
                "#1098ad",
                lead=3000,
                lag=6000,
                groups=("kick_type", "players", "zone", "outcome"),
            ),
            _button(
                "Penalty",
                "p",
                "#fab005",
                lead=4000,
                lag=4000,
                groups=("infringement", "team", "zone"),
            ),
            _button("Try", "y", "#d6336c", lead=10000, lag=5000, groups=("team", "players")),
            _button(
                "Conversion",
                "v",
                "#7950f2",
                lead=3000,
                lag=6000,
                groups=("outcome", "team", "players"),
            ),
        ],
    )


def sevens_template() -> TemplateContent:
    return TemplateContent(
        name="Rugby sevens",
        descriptor_groups=_groups(),
        outcome_group="outcome",
        success_values=["Won"],
        buttons=[
            _button("Kickoff", "1", "#1971c2", lead=2000, lag=8000, groups=("team", "zone")),
            _button("Scrum", "2", "#e8590c", kind="span", groups=("outcome", "team", "zone")),
            _button("Lineout", "3", "#f08c00", kind="span", groups=("outcome", "team", "zone")),
            _button(
                "Ruck", "5", "#2f9e44", lead=2000, lag=3000, groups=("outcome", "team", "zone")
            ),
            _button("Possession", "6", "#868e96", kind="span", groups=("team", "zone")),
            _button("Carry", "c", "#0ca678", groups=("players", "zone")),
            _button("Line break", "b", "#e03131", lead=3000, lag=6000, groups=("players", "zone")),
            _button("Tackle", "t", "#5c7cfa", groups=("tackle", "players", "zone")),
            _button("Turnover", "o", "#c2255c", groups=("turnover", "team", "zone")),
            _button(
                "Kick",
                "x",
                "#1098ad",
                lead=3000,
                lag=6000,
                groups=("kick_type", "players", "zone", "outcome"),
            ),
            _button("Penalty", "p", "#fab005", groups=("infringement", "team", "zone")),
            _button("Try", "y", "#d6336c", lead=8000, lag=4000, groups=("team", "players")),
            _button(
                "Conversion",
                "v",
                "#7950f2",
                lead=2000,
                lag=5000,
                groups=("outcome", "team", "players"),
            ),
        ],
    )


def default_templates() -> list[TemplateContent]:
    return [fifteens_template(), sevens_template()]
