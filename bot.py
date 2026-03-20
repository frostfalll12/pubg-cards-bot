import os
import sqlite3

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")

SECTIONS = {
    "evolving": {
        "name": "Evolving Universe",
        "total": 16,
        "cards": [
            "s-rank vault",
            "a-rank vault",
            "b-rank vault",
            "anniversary lucky spin",
            "energy shield",
            "spatial distortion zone 1",
            "spatial distortion zone 2",
            "floating thruster",
            "racing hall",
            "dynamic slide rail",
            "parachute challenge",
            "racing challenge",
            "music hall",
            "evacuation master",
            "melody strongest team",
            "raging rush strongest team",
        ],
    },
    "jujutsu": {
        "name": "Jujutsu Kaisen",
        "total": 11,
        "cards": [
            "yuji itadori",
            "megumi fushiguro",
            "nobara kugisaki",
            "satoru gojo",
            "jujutsu kaisen",
            "ryomen sukuna",
            "suguru geto",
            "nue",
            "cathy",
            "cursed corpse bear",
            "inverted spear of heaven",
        ],
    },
    "anniversary": {
        "name": "Anniversary",
        "total": 10,
        "cards": [
            "rhythm hero",
            "vibrant world",
            "dino ground",
            "ocean odyssey",
            "immortal honor",
            "pro collector",
            "golden age",
            "arcade time",
            "golden dynasty",
        ],
    },
    "pmgc": {
        "name": "2025 PMGC",
        "total": 22,
        "cards": [
            "mad",
            "ea",
            "r8",
            "kara",
            "vpe",
            "fl",
            "goat",
            "reg",
            "dx",
            "ae",
            "tt",
            "dk",
            "drx",
            "champion a7",
            "2nd place ulf",
            "3rd place apg",
            "bangkok thailand",
        ],
    },
    "playful": {
        "name": "Playful Battleground",
        "total": 11,
        "cards": [
            "mrbeast",
            "ray",
            "garand",
            "tracked amphicarrier",
        ],
    },
}

if not TOKEN:
    raise RuntimeError("TOKEN not found. Put TOKEN=your_bot_token in your .env file.")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

db = sqlite3.connect("/data/cards.db")
cur = db.cursor()
cur.execute(
    """
    CREATE TABLE IF NOT EXISTS user_cards (
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        section TEXT NOT NULL,
        card_name TEXT NOT NULL,
        list_type TEXT NOT NULL CHECK(list_type IN ('missing', 'dupe')),
        amount INTEGER NOT NULL DEFAULT 1,
        UNIQUE(guild_id, user_id, section, card_name, list_type)
    )
    """
)
db.commit()


def normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


def get_visible_cards(section_key: str) -> list[str]:
    return SECTIONS[section_key]["cards"]


def get_missing_set(guild_id: int, user_id: int, section: str) -> set[str]:
    cur.execute(
        """
        SELECT card_name
        FROM user_cards
        WHERE guild_id=? AND user_id=? AND section=? AND list_type='missing'
        """,
        (guild_id, user_id, section),
    )
    return {row[0] for row in cur.fetchall()}


def get_dupe_map(guild_id: int, user_id: int, section: str) -> dict[str, int]:
    cur.execute(
        """
        SELECT card_name, amount
        FROM user_cards
        WHERE guild_id=? AND user_id=? AND section=? AND list_type='dupe'
        """,
        (guild_id, user_id, section),
    )
    return {row[0]: row[1] for row in cur.fetchall()}


def replace_missing_section(guild_id: int, user_id: int, section: str, cards: set[str]) -> None:
    valid_cards = set(get_visible_cards(section))
    cleaned = sorted({normalize(card) for card in cards if normalize(card) in valid_cards})

    cur.execute(
        """
        DELETE FROM user_cards
        WHERE guild_id=? AND user_id=? AND section=? AND list_type='missing'
        """,
        (guild_id, user_id, section),
    )

    for card in cleaned:
        cur.execute(
            """
            INSERT OR IGNORE INTO user_cards
            (guild_id, user_id, section, card_name, list_type, amount)
            VALUES (?, ?, ?, ?, 'missing', 1)
            """,
            (guild_id, user_id, section, card),
        )

    db.commit()


def replace_dupe_section(guild_id: int, user_id: int, section: str, dupe_map: dict[str, int]) -> None:
    valid_cards = set(get_visible_cards(section))
    cleaned = {}
    for card, amount in dupe_map.items():
        card = normalize(card)
        if card in valid_cards and int(amount) > 0:
            cleaned[card] = int(amount)

    cur.execute(
        """
        DELETE FROM user_cards
        WHERE guild_id=? AND user_id=? AND section=? AND list_type='dupe'
        """,
        (guild_id, user_id, section),
    )

    for card, amount in cleaned.items():
        cur.execute(
            """
            INSERT OR REPLACE INTO user_cards
            (guild_id, user_id, section, card_name, list_type, amount)
            VALUES (?, ?, ?, ?, 'dupe', ?)
            """,
            (guild_id, user_id, section, card, amount),
        )

    db.commit()


def build_collection_embed(member: discord.Member, guild_id: int) -> discord.Embed:
    embed = discord.Embed(
        title=f"📘 {member.display_name}'s Collection",
        color=discord.Color.blurple(),
    )

    for section_key, data in SECTIONS.items():
        released_cards = set(data["cards"])
        missing = set(get_missing_set(guild_id, member.id, section_key))
        dupes = get_dupe_map(guild_id, member.id, section_key)

        owned_count = len(released_cards - missing)
        total = data["total"]
        percent = int((owned_count / total) * 100) if total else 0

        missing_text = ", ".join(card.title() for card in sorted(missing)) if missing else "None"
        dupes_text = "\n".join(f"{card.title()} x{amt}" for card, amt in sorted(dupes.items())) if dupes else "None"

        value = (
            f"🟢 **Owned:** {owned_count}/{total} ({percent}%)\n\n"
            f"🔴 **Missing ({len(missing)}):**\n{missing_text}\n\n"
            f"🟡 **Duplicates:**\n{dupes_text}"
        )

        embed.add_field(
            name=f"📦 {data['name']}",
            value=value[:1024],
            inline=False,
        )

    embed.set_footer(text="Use /info to learn how the bot works.")
    return embed


def build_missing_summary(pending_missing: dict[str, set[str]], header: str) -> str:
    lines = [header, ""]
    total_selected = sum(len(cards) for cards in pending_missing.values())

    if total_selected == 0:
        lines.append("No pending missing cards selected yet.")
        return "\n".join(lines)

    lines.append(f"**Pending missing cards ({total_selected})**")
    for section_key, data in SECTIONS.items():
        cards = pending_missing.get(section_key, set())
        if cards:
            card_list = ", ".join(card.title() for card in sorted(cards))
            lines.append(f"• **{data['name']}**: {card_list}")

    return "\n".join(lines)


def build_dupe_add_summary(pending_dupes: dict[str, dict[str, int]], header: str) -> str:
    lines = [header, ""]
    total_entries = sum(len(cards) for cards in pending_dupes.values())

    if total_entries == 0:
        lines.append("No pending duplicate cards selected yet.")
        return "\n".join(lines)

    lines.append("**Pending duplicates**")
    for section_key, data in SECTIONS.items():
        cards = pending_dupes.get(section_key, {})
        if cards:
            card_list = ", ".join(f"{card.title()} x{amt}" for card, amt in sorted(cards.items()))
            lines.append(f"• **{data['name']}**: {card_list}")

    return "\n".join(lines)


def build_dupe_remove_summary(removal_map: dict[str, dict[str, int]], header: str) -> str:
    lines = [header, ""]
    total_entries = sum(len(cards) for cards in removal_map.values())

    if total_entries == 0:
        lines.append("No pending duplicate removals selected yet.")
        return "\n".join(lines)

    lines.append("**Pending duplicate removals**")
    for section_key, data in SECTIONS.items():
        cards = removal_map.get(section_key, {})
        if cards:
            card_list = ", ".join(f"{card.title()} -{amt}" for card, amt in sorted(cards.items()))
            lines.append(f"• **{data['name']}**: {card_list}")

    return "\n".join(lines)


class MissingSectionSelect(discord.ui.Select):
    def __init__(self, pending_missing: dict[str, set[str]]):
        self.pending_missing = pending_missing
        options = [discord.SelectOption(label=data["name"], value=key) for key, data in SECTIONS.items()]
        super().__init__(placeholder="Select a section", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        section = self.values[0]
        await interaction.response.edit_message(
            content=build_missing_summary(
                self.pending_missing,
                f"Editing missing cards for **{SECTIONS[section]['name']}**",
            ),
            view=MissingSectionEditView(section, self.pending_missing),
        )


class MissingSectionPickerView(discord.ui.View):
    def __init__(self, pending_missing: dict[str, set[str]]):
        super().__init__(timeout=300)
        self.pending_missing = pending_missing
        self.add_item(MissingSectionSelect(pending_missing))

    @discord.ui.button(label="Save All", emoji="✅", style=discord.ButtonStyle.green, row=4)
    async def save_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        for section_key in SECTIONS:
            replace_missing_section(
                interaction.guild_id,
                interaction.user.id,
                section_key,
                self.pending_missing.get(section_key, set()),
            )
        await interaction.response.edit_message(content="✅ Saved all missing-card changes.", view=None)

    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.red, row=4)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="❌ Cancelled. Pending missing changes were not saved.",
            view=None,
        )


class MissingSectionCardSelect(discord.ui.Select):
    def __init__(self, section: str, pending_missing: dict[str, set[str]]):
        self.section = section
        self.pending_missing = pending_missing
        current_selected = pending_missing.get(section, set())

        options = [
            discord.SelectOption(
                label=card.title(),
                value=card,
                default=(card in current_selected),
            )
            for card in get_visible_cards(section)[:25]
        ]

        super().__init__(
            placeholder="Select missing cards for this section",
            min_values=0,
            max_values=len(options),
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        self.pending_missing[self.section] = set(self.values)
        await interaction.response.edit_message(
            content=build_missing_summary(
                self.pending_missing,
                f"Updated **{SECTIONS[self.section]['name']}**. Keep editing, go to sections, save all, or cancel.",
            ),
            view=MissingSectionEditView(self.section, self.pending_missing),
        )


class MissingSectionEditView(discord.ui.View):
    def __init__(self, section: str, pending_missing: dict[str, set[str]]):
        super().__init__(timeout=300)
        self.section = section
        self.pending_missing = pending_missing
        self.add_item(MissingSectionCardSelect(section, pending_missing))

    @discord.ui.button(label="Sections", emoji="↩️", style=discord.ButtonStyle.secondary, row=4)
    async def sections(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content=build_missing_summary(self.pending_missing, "Choose another section."),
            view=MissingSectionPickerView(self.pending_missing),
        )

    @discord.ui.button(label="Clear Section", emoji="🗑️", style=discord.ButtonStyle.secondary, row=4)
    async def clear_section(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.pending_missing[self.section] = set()
        await interaction.response.edit_message(
            content=build_missing_summary(
                self.pending_missing,
                f"Cleared pending picks for **{SECTIONS[self.section]['name']}**.",
            ),
            view=MissingSectionEditView(self.section, self.pending_missing),
        )

    @discord.ui.button(label="Save All", emoji="✅", style=discord.ButtonStyle.green, row=4)
    async def save_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        for section_key in SECTIONS:
            replace_missing_section(
                interaction.guild_id,
                interaction.user.id,
                section_key,
                self.pending_missing.get(section_key, set()),
            )
        await interaction.response.edit_message(content="✅ Saved all missing-card changes.", view=None)

    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.red, row=4)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="❌ Cancelled. Pending missing changes were not saved.",
            view=None,
        )


class MissingRemoveSectionSelect(discord.ui.Select):
    def __init__(self, pending_missing: dict[str, set[str]]):
        self.pending_missing = pending_missing
        available_sections = [(key, cards) for key, cards in pending_missing.items() if cards]

        if available_sections:
            options = [
                discord.SelectOption(label=SECTIONS[key]["name"], value=key)
                for key, _cards in available_sections
            ]
        else:
            options = [discord.SelectOption(label="No missing sections available", value="__none__")]

        super().__init__(placeholder="Select a section", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        section = self.values[0]
        if section == "__none__":
            await interaction.response.send_message("You do not have any missing cards saved.", ephemeral=True)
            return

        await interaction.response.edit_message(
            content=build_missing_summary(
                self.pending_missing,
                f"Removing missing cards in **{SECTIONS[section]['name']}**",
            ),
            view=MissingRemoveSectionEditView(section, self.pending_missing),
        )


class MissingRemoveSectionPickerView(discord.ui.View):
    def __init__(self, pending_missing: dict[str, set[str]]):
        super().__init__(timeout=300)
        self.pending_missing = pending_missing
        self.add_item(MissingRemoveSectionSelect(pending_missing))

    @discord.ui.button(label="Save All", emoji="✅", style=discord.ButtonStyle.green, row=4)
    async def save_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        for section_key in SECTIONS:
            replace_missing_section(
                interaction.guild_id,
                interaction.user.id,
                section_key,
                self.pending_missing.get(section_key, set()),
            )
        await interaction.response.edit_message(content="✅ Saved all missing-card removals.", view=None)

    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.red, row=4)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="❌ Cancelled. Pending missing removals were not saved.",
            view=None,
        )


class MissingRemoveSectionCardSelect(discord.ui.Select):
    def __init__(self, section: str, pending_missing: dict[str, set[str]]):
        self.section = section
        self.pending_missing = pending_missing
        current_selected = pending_missing.get(section, set())

        options = [
            discord.SelectOption(
                label=card.title(),
                value=card,
                default=(card in current_selected),
            )
            for card in sorted(current_selected)
        ]

        if not options:
            options = [discord.SelectOption(label="No missing cards in this section", value="__none__")]

        super().__init__(
            placeholder="Uncheck cards you no longer want missing",
            min_values=0 if options[0].value != "__none__" else 1,
            max_values=len(options),
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        if "__none__" in self.values:
            await interaction.response.send_message("No missing cards in this section.", ephemeral=True)
            return

        self.pending_missing[self.section] = set(self.values)
        await interaction.response.edit_message(
            content=build_missing_summary(
                self.pending_missing,
                f"Updated **{SECTIONS[self.section]['name']}**. Keep editing, go to sections, save all, or cancel.",
            ),
            view=MissingRemoveSectionEditView(self.section, self.pending_missing),
        )


class MissingRemoveSectionEditView(discord.ui.View):
    def __init__(self, section: str, pending_missing: dict[str, set[str]]):
        super().__init__(timeout=300)
        self.section = section
        self.pending_missing = pending_missing
        self.add_item(MissingRemoveSectionCardSelect(section, pending_missing))

    @discord.ui.button(label="Sections", emoji="↩️", style=discord.ButtonStyle.secondary, row=4)
    async def sections(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content=build_missing_summary(self.pending_missing, "Choose another section."),
            view=MissingRemoveSectionPickerView(self.pending_missing),
        )

    @discord.ui.button(label="Clear Section", emoji="🗑️", style=discord.ButtonStyle.secondary, row=4)
    async def clear_section(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.pending_missing[self.section] = set()
        await interaction.response.edit_message(
            content=build_missing_summary(
                self.pending_missing,
                f"Cleared pending picks for **{SECTIONS[self.section]['name']}**.",
            ),
            view=MissingRemoveSectionEditView(self.section, self.pending_missing),
        )

    @discord.ui.button(label="Save All", emoji="✅", style=discord.ButtonStyle.green, row=4)
    async def save_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        for section_key in SECTIONS:
            replace_missing_section(
                interaction.guild_id,
                interaction.user.id,
                section_key,
                self.pending_missing.get(section_key, set()),
            )
        await interaction.response.edit_message(content="✅ Saved all missing-card removals.", view=None)

    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.red, row=4)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="❌ Cancelled. Pending missing removals were not saved.",
            view=None,
        )


class DupeAddSectionSelect(discord.ui.Select):
    def __init__(self, pending_dupes: dict[str, dict[str, int]]):
        self.pending_dupes = pending_dupes
        options = [discord.SelectOption(label=data["name"], value=key) for key, data in SECTIONS.items()]
        super().__init__(placeholder="Select a section", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        section = self.values[0]
        await interaction.response.edit_message(
            content=build_dupe_add_summary(
                self.pending_dupes,
                f"Adding duplicates in **{SECTIONS[section]['name']}**",
            ),
            view=DupeAddSectionView(section, self.pending_dupes),
        )


class DupeAddSectionPickerView(discord.ui.View):
    def __init__(self, pending_dupes: dict[str, dict[str, int]]):
        super().__init__(timeout=300)
        self.pending_dupes = pending_dupes
        self.add_item(DupeAddSectionSelect(pending_dupes))

    @discord.ui.button(label="Save All", emoji="✅", style=discord.ButtonStyle.green, row=4)
    async def save_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        for section_key in SECTIONS:
            current_db_dupes = dict(get_dupe_map(interaction.guild_id, interaction.user.id, section_key))
            pending = self.pending_dupes.get(section_key, {})
            merged = dict(current_db_dupes)

            for card, amount in pending.items():
                merged[card] = merged.get(card, 0) + amount

            replace_dupe_section(interaction.guild_id, interaction.user.id, section_key, merged)

        await interaction.response.edit_message(content="✅ Saved all duplicate additions.", view=None)

    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.red, row=4)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="❌ Cancelled. Pending duplicate additions were not saved.",
            view=None,
        )


class DupeCardSelect(discord.ui.Select):
    def __init__(self, section: str, pending_dupes: dict[str, dict[str, int]], selected_card: str | None = None):
        self.section = section
        self.pending_dupes = pending_dupes
        options = [
            discord.SelectOption(label=card.title(), value=card, default=(card == selected_card))
            for card in get_visible_cards(section)[:25]
        ]
        super().__init__(placeholder="Select one duplicate card", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_card = self.values[0]
        await interaction.response.edit_message(
            content=build_dupe_add_summary(
                self.pending_dupes,
                f"Selected **{selected_card.title()}** in **{SECTIONS[self.section]['name']}**. Choose amount.",
            ),
            view=DupeAddAmountView(self.section, self.pending_dupes, selected_card),
        )


class DupeAmountSelect(discord.ui.Select):
    def __init__(self, section: str, pending_dupes: dict[str, dict[str, int]], selected_card: str):
        self.section = section
        self.pending_dupes = pending_dupes
        self.selected_card = selected_card
        options = [discord.SelectOption(label=f"+{i}", value=str(i)) for i in range(1, 11)]
        super().__init__(placeholder="Select amount to add", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        amount = int(self.values[0])
        current = self.pending_dupes.setdefault(self.section, {}).get(self.selected_card, 0)
        self.pending_dupes.setdefault(self.section, {})[self.selected_card] = current + amount

        await interaction.response.edit_message(
            content=build_dupe_add_summary(
                self.pending_dupes,
                f"Added **{self.selected_card.title()} x{amount}** to pending duplicates.",
            ),
            view=DupeAddSectionView(self.section, self.pending_dupes),
        )


class DupeAddSectionView(discord.ui.View):
    def __init__(self, section: str, pending_dupes: dict[str, dict[str, int]]):
        super().__init__(timeout=300)
        self.section = section
        self.pending_dupes = pending_dupes
        self.add_item(DupeCardSelect(section, pending_dupes))

    @discord.ui.button(label="Sections", emoji="↩️", style=discord.ButtonStyle.secondary, row=4)
    async def sections(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content=build_dupe_add_summary(self.pending_dupes, "Choose another section."),
            view=DupeAddSectionPickerView(self.pending_dupes),
        )

    @discord.ui.button(label="Save All", emoji="✅", style=discord.ButtonStyle.green, row=4)
    async def save_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        for section_key in SECTIONS:
            current_db_dupes = dict(get_dupe_map(interaction.guild_id, interaction.user.id, section_key))
            pending = self.pending_dupes.get(section_key, {})
            merged = dict(current_db_dupes)

            for card, amount in pending.items():
                merged[card] = merged.get(card, 0) + amount

            replace_dupe_section(interaction.guild_id, interaction.user.id, section_key, merged)

        await interaction.response.edit_message(content="✅ Saved all duplicate additions.", view=None)

    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.red, row=4)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="❌ Cancelled. Pending duplicate additions were not saved.",
            view=None,
        )


class DupeAddAmountView(discord.ui.View):
    def __init__(self, section: str, pending_dupes: dict[str, dict[str, int]], selected_card: str):
        super().__init__(timeout=300)
        self.section = section
        self.pending_dupes = pending_dupes
        self.selected_card = selected_card
        self.add_item(DupeCardSelect(section, pending_dupes, selected_card))
        self.add_item(DupeAmountSelect(section, pending_dupes, selected_card))

    @discord.ui.button(label="Sections", emoji="↩️", style=discord.ButtonStyle.secondary, row=4)
    async def sections(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content=build_dupe_add_summary(self.pending_dupes, "Choose another section."),
            view=DupeAddSectionPickerView(self.pending_dupes),
        )

    @discord.ui.button(label="Clear Card", emoji="🗑️", style=discord.ButtonStyle.secondary, row=4)
    async def clear_card(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.section in self.pending_dupes and self.selected_card in self.pending_dupes[self.section]:
            del self.pending_dupes[self.section][self.selected_card]
            if not self.pending_dupes[self.section]:
                del self.pending_dupes[self.section]

        await interaction.response.edit_message(
            content=build_dupe_add_summary(
                self.pending_dupes,
                f"Cleared pending duplicate for **{self.selected_card.title()}**.",
            ),
            view=DupeAddSectionView(self.section, self.pending_dupes),
        )

    @discord.ui.button(label="Save All", emoji="✅", style=discord.ButtonStyle.green, row=4)
    async def save_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        for section_key in SECTIONS:
            current_db_dupes = dict(get_dupe_map(interaction.guild_id, interaction.user.id, section_key))
            pending = self.pending_dupes.get(section_key, {})
            merged = dict(current_db_dupes)

            for card, amount in pending.items():
                merged[card] = merged.get(card, 0) + amount

            replace_dupe_section(interaction.guild_id, interaction.user.id, section_key, merged)

        await interaction.response.edit_message(content="✅ Saved all duplicate additions.", view=None)

    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.red, row=4)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="❌ Cancelled. Pending duplicate additions were not saved.",
            view=None,
        )


class DupeRemoveSectionSelect(discord.ui.Select):
    def __init__(self, base_dupes: dict[str, dict[str, int]], removal_map: dict[str, dict[str, int]]):
        self.base_dupes = base_dupes
        self.removal_map = removal_map

        available_sections = []
        for section_key, cards in base_dupes.items():
            has_removable = False
            for card, amount in cards.items():
                already_removed = removal_map.get(section_key, {}).get(card, 0)
                if amount - already_removed > 0:
                    has_removable = True
                    break
            if has_removable:
                available_sections.append(section_key)

        if available_sections:
            options = [discord.SelectOption(label=SECTIONS[key]["name"], value=key) for key in available_sections]
        else:
            options = [discord.SelectOption(label="No duplicate sections available", value="__none__")]

        super().__init__(placeholder="Select a section", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        section = self.values[0]
        if section == "__none__":
            await interaction.response.send_message(
                "You do not have any duplicate cards available to remove.",
                ephemeral=True,
            )
            return

        await interaction.response.edit_message(
            content=build_dupe_remove_summary(
                self.removal_map,
                f"Removing duplicates in **{SECTIONS[section]['name']}**",
            ),
            view=DupeRemoveSectionView(section, self.base_dupes, self.removal_map),
        )


class DupeRemoveSectionPickerView(discord.ui.View):
    def __init__(self, base_dupes: dict[str, dict[str, int]], removal_map: dict[str, dict[str, int]]):
        super().__init__(timeout=300)
        self.base_dupes = base_dupes
        self.removal_map = removal_map
        self.add_item(DupeRemoveSectionSelect(base_dupes, removal_map))

    @discord.ui.button(label="Save All", emoji="✅", style=discord.ButtonStyle.green, row=4)
    async def save_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        for section_key in SECTIONS:
            current_map = dict(self.base_dupes.get(section_key, {}))
            removals = self.removal_map.get(section_key, {})

            for card, amount in removals.items():
                if card in current_map:
                    current_map[card] = max(0, current_map[card] - amount)
                    if current_map[card] == 0:
                        del current_map[card]

            replace_dupe_section(interaction.guild_id, interaction.user.id, section_key, current_map)

        await interaction.response.edit_message(content="✅ Saved all duplicate removals.", view=None)

    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.red, row=4)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="❌ Cancelled. Pending duplicate removals were not saved.",
            view=None,
        )


class ExistingDupeCardSelect(discord.ui.Select):
    def __init__(
        self,
        section: str,
        base_dupes: dict[str, dict[str, int]],
        removal_map: dict[str, dict[str, int]],
        selected_card: str | None = None,
    ):
        self.section = section
        self.base_dupes = base_dupes
        self.removal_map = removal_map

        effective_cards = []
        for card, amount in sorted(base_dupes.get(section, {}).items()):
            already_removed = removal_map.get(section, {}).get(card, 0)
            remaining = amount - already_removed
            if remaining > 0:
                effective_cards.append((card, remaining))

        if effective_cards:
            options = [
                discord.SelectOption(
                    label=f"{card.title()} x{remaining}",
                    value=card,
                    default=(card == selected_card),
                    description=f"Remaining duplicates: {remaining}",
                )
                for card, remaining in effective_cards[:25]
            ]
        else:
            options = [discord.SelectOption(label="No duplicate cards available", value="__none__")]

        super().__init__(placeholder="Select one duplicate card", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_card = self.values[0]
        if selected_card == "__none__":
            await interaction.response.send_message("No duplicate cards available in this section.", ephemeral=True)
            return

        base_amount = self.base_dupes.get(self.section, {}).get(selected_card, 0)
        already_removed = self.removal_map.get(self.section, {}).get(selected_card, 0)
        remaining = base_amount - already_removed

        await interaction.response.edit_message(
            content=build_dupe_remove_summary(
                self.removal_map,
                f"Selected **{selected_card.title()}** with **x{remaining}** remaining in **{SECTIONS[self.section]['name']}**.",
            ),
            view=DupeRemoveAmountView(
                self.section,
                self.base_dupes,
                self.removal_map,
                selected_card,
                remaining,
            ),
        )


class DupeRemoveAmountSelect(discord.ui.Select):
    def __init__(
        self,
        section: str,
        base_dupes: dict[str, dict[str, int]],
        removal_map: dict[str, dict[str, int]],
        selected_card: str,
        remaining_amount: int,
    ):
        self.section = section
        self.base_dupes = base_dupes
        self.removal_map = removal_map
        self.selected_card = selected_card
        self.remaining_amount = remaining_amount

        max_select = min(remaining_amount, 25)
        options = [discord.SelectOption(label=f"-{i}", value=str(i)) for i in range(1, max_select + 1)]
        super().__init__(placeholder="Select amount to remove", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        amount = int(self.values[0])
        self.removal_map.setdefault(self.section, {})[self.selected_card] = amount

        await interaction.response.edit_message(
            content=build_dupe_remove_summary(
                self.removal_map,
                f"Set **{self.selected_card.title()}** to remove **-{amount}**.",
            ),
            view=DupeRemoveSectionView(self.section, self.base_dupes, self.removal_map),
        )


class DupeRemoveSectionView(discord.ui.View):
    def __init__(self, section: str, base_dupes: dict[str, dict[str, int]], removal_map: dict[str, dict[str, int]]):
        super().__init__(timeout=300)
        self.section = section
        self.base_dupes = base_dupes
        self.removal_map = removal_map
        self.add_item(ExistingDupeCardSelect(section, base_dupes, removal_map))

    @discord.ui.button(label="Sections", emoji="↩️", style=discord.ButtonStyle.secondary, row=4)
    async def sections(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content=build_dupe_remove_summary(self.removal_map, "Choose another section."),
            view=DupeRemoveSectionPickerView(self.base_dupes, self.removal_map),
        )

    @discord.ui.button(label="Save All", emoji="✅", style=discord.ButtonStyle.green, row=4)
    async def save_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        for section_key in SECTIONS:
            current_map = dict(self.base_dupes.get(section_key, {}))
            removals = self.removal_map.get(section_key, {})

            for card, amount in removals.items():
                if card in current_map:
                    current_map[card] = max(0, current_map[card] - amount)
                    if current_map[card] == 0:
                        del current_map[card]

            replace_dupe_section(interaction.guild_id, interaction.user.id, section_key, current_map)

        await interaction.response.edit_message(content="✅ Saved all duplicate removals.", view=None)

    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.red, row=4)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="❌ Cancelled. Pending duplicate removals were not saved.",
            view=None,
        )


class DupeRemoveAmountView(discord.ui.View):
    def __init__(
        self,
        section: str,
        base_dupes: dict[str, dict[str, int]],
        removal_map: dict[str, dict[str, int]],
        selected_card: str,
        remaining_amount: int,
    ):
        super().__init__(timeout=300)
        self.section = section
        self.base_dupes = base_dupes
        self.removal_map = removal_map
        self.selected_card = selected_card
        self.remaining_amount = remaining_amount

        self.add_item(ExistingDupeCardSelect(section, base_dupes, removal_map, selected_card))
        self.add_item(DupeRemoveAmountSelect(section, base_dupes, removal_map, selected_card, remaining_amount))

    @discord.ui.button(label="Sections", emoji="↩️", style=discord.ButtonStyle.secondary, row=4)
    async def sections(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content=build_dupe_remove_summary(self.removal_map, "Choose another section."),
            view=DupeRemoveSectionPickerView(self.base_dupes, self.removal_map),
        )

    @discord.ui.button(label="Clear Card", emoji="🗑️", style=discord.ButtonStyle.secondary, row=4)
    async def clear_card(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.section in self.removal_map and self.selected_card in self.removal_map[self.section]:
            del self.removal_map[self.section][self.selected_card]
            if not self.removal_map[self.section]:
                del self.removal_map[self.section]

        await interaction.response.edit_message(
            content=build_dupe_remove_summary(
                self.removal_map,
                f"Cleared pending removal for **{self.selected_card.title()}**.",
            ),
            view=DupeRemoveSectionView(self.section, self.base_dupes, self.removal_map),
        )

    @discord.ui.button(label="Save All", emoji="✅", style=discord.ButtonStyle.green, row=4)
    async def save_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        for section_key in SECTIONS:
            current_map = dict(self.base_dupes.get(section_key, {}))
            removals = self.removal_map.get(section_key, {})

            for card, amount in removals.items():
                if card in current_map:
                    current_map[card] = max(0, current_map[card] - amount)
                    if current_map[card] == 0:
                        del current_map[card]

            replace_dupe_section(interaction.guild_id, interaction.user.id, section_key, current_map)

        await interaction.response.edit_message(content="✅ Saved all duplicate removals.", view=None)

    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.red, row=4)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="❌ Cancelled. Pending duplicate removals were not saved.",
            view=None,
        )


missing_group = app_commands.Group(name="missing", description="Manage your missing cards")
dupes_group = app_commands.Group(name="dupes", description="Manage your duplicate cards")


@missing_group.command(name="add", description="Add missing cards")
async def missing_add(interaction: discord.Interaction):
    current_missing = {
        section_key: set(get_missing_set(interaction.guild_id, interaction.user.id, section_key))
        for section_key in SECTIONS
    }
    await interaction.response.send_message(
        build_missing_summary(current_missing, "Choose a section."),
        view=MissingSectionPickerView(current_missing),
        ephemeral=True,
    )


@missing_group.command(name="remove", description="Remove missing cards")
async def missing_remove(interaction: discord.Interaction):
    current_missing = {
        section_key: set(get_missing_set(interaction.guild_id, interaction.user.id, section_key))
        for section_key in SECTIONS
    }
    available_sections = {k: v for k, v in current_missing.items() if v}

    if not available_sections:
        await interaction.response.send_message("You do not have any missing cards saved.", ephemeral=True)
        return

    await interaction.response.send_message(
        build_missing_summary(available_sections, "Choose a section."),
        view=MissingRemoveSectionPickerView(available_sections),
        ephemeral=True,
    )


@dupes_group.command(name="add", description="Add duplicate cards")
async def dupes_add(interaction: discord.Interaction):
    pending_dupes: dict[str, dict[str, int]] = {}
    await interaction.response.send_message(
        build_dupe_add_summary(pending_dupes, "Choose a section."),
        view=DupeAddSectionPickerView(pending_dupes),
        ephemeral=True,
    )


@dupes_group.command(name="remove", description="Remove duplicate cards")
async def dupes_remove(interaction: discord.Interaction):
    base_dupes = {
        section_key: dict(get_dupe_map(interaction.guild_id, interaction.user.id, section_key))
        for section_key in SECTIONS
    }
    available_sections = {k: v for k, v in base_dupes.items() if v}

    if not available_sections:
        await interaction.response.send_message("You do not have any duplicate cards saved.", ephemeral=True)
        return

    removal_map: dict[str, dict[str, int]] = {}
    await interaction.response.send_message(
        build_dupe_remove_summary(removal_map, "Choose a section."),
        view=DupeRemoveSectionPickerView(available_sections, removal_map),
        ephemeral=True,
    )


@bot.tree.command(name="collection", description="Show your collection or another user's collection")
async def collection(interaction: discord.Interaction, user: discord.Member | None = None):
    target = user or interaction.user
    embed = build_collection_embed(target, interaction.guild_id)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="info", description="Learn how to use the PUBG cards bot")
async def info(interaction: discord.Interaction):
    embed = discord.Embed(
        title="ℹ️ PUBG Cards Bot Info",
        description="Track your missing cards and duplicate cards by section.",
        color=discord.Color.blurple(),
    )

    embed.add_field(
        name="Important",
        value=(
            "You must add **all** your missing cards.\n"
            "The bot calculates owned cards as:\n"
            "**Owned = Released cards - Missing**\n\n"
            "If your missing list is incomplete, your collection will be wrong."
        ),
        inline=False,
    )

    embed.add_field(
        name="Commands",
        value=(
            "`/missing add` - edit your missing cards\n"
            "`/missing remove` - remove cards from your missing list\n"
            "`/dupes add` - add duplicate cards and amounts\n"
            "`/dupes remove` - remove duplicate cards and amounts\n"
            "`/collection` - show your collection\n"
            "`/collection user:@someone` - show someone else's collection\n"
            "`/info` - show this help message"
        ),
        inline=False,
    )

    embed.add_field(
        name="What the bot shows",
        value=(
            "• Total owned count\n"
            "• Missing cards\n"
            "• Duplicate cards\n\n"
            "It does **not** list every owned card individually."
        ),
        inline=False,
    )

    embed.add_field(
        name="About totals",
        value=(
            "Some sections may have a higher total than the currently released cards.\n"
            "So you may not reach 100% until PUBG releases the remaining cards."
        ),
        inline=False,
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup_bot_commands():
    try:
        bot.tree.add_command(missing_group)
    except Exception:
        pass
    try:
        bot.tree.add_command(dupes_group)
    except Exception:
        pass


@bot.event
async def on_ready():
    await setup_bot_commands()
    synced = await bot.tree.sync()
    print(f"Logged in as {bot.user}")
    print(f"Synced {len(synced)} commands")


bot.run(TOKEN)