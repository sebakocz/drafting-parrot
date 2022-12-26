from Database.Models.settings import Settings


def settings_field(settings: Settings):
    return {
        "name": "Settings",
        "value": (
            f"pick type: **{settings.pick_type}**\n"
            f"packs per player: **{settings.packs_per_player}**\n"
            f"cards per pack: **{settings.cards_per_pack}**\n"
            f"time per pick: **{settings.seconds_per_pick}** seconds\n"
        ),
    }


def players_field(draft):
    return {
        "name": f"Players ({len(draft.participants)}/{draft.max_participants})",
        "value": "".join([f"<@{user.discord_id}>\n" for user in draft.participants]) or "No players yet. Come join!",
        "inline": False
    }
