import asyncio
import logging
import re
import aiohttp
import requests

uid_regex = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


class ApiError(Exception):
    def __init__(self, message):
        self.message = message

async def get_card_data(draft_cardpool_lines):
    public_cards = requests.get("https://server.collective.gg/api/public-cards/").json()

    loaded_cardpool = []
    tasks = []
    results = []
    async with aiohttp.ClientSession() as session:
        logging.info(f"Loading {len(draft_cardpool_lines)} cards...")
        for line in draft_cardpool_lines:
            card_name, card_link = None, None
            try:
                card_id = re.search(uid_regex, line).group(0)
            except AttributeError:
                card_id = None

            if card_id:
                tasks.append(
                    asyncio.create_task(
                        session.get(f"https://server.collective.gg/api/card/{card_id}")
                    )
                )

            else:
                for public_card in public_cards["cards"]:
                    if public_card["name"].rstrip() == line.rstrip():
                        card_name = public_card["name"]
                        card_link = public_card["imgurl"]
                        break

                if card_name and card_link:
                    loaded_cardpool.append({"name": card_name, "link": card_link})
                else:
                    # cancel all tasks
                    for task in tasks:
                        task.cancel()

                    raise ApiError(f"Could not find card in public list: {line}")

        responses = await asyncio.gather(*tasks)
        for response, line in zip(responses, draft_cardpool_lines):
            if response.status != 200:
                raise ApiError(f"Error loading line: **{line}**")
            else:
                results.append(await response.json())

        for result in results:
            card_json = result
            card_name = card_json["card"]["name"]
            card_id = card_json["card"]["UID"]

            # create card_link
            # suffix -m or -s is based on whether the card has externals
            if len(card_json["externals"]) > 0:
                externals_suffix = "-m"
            else:
                externals_suffix = "-s"

            card_link = (
                f"https://files.collective.gg/p/cards/{card_id}{externals_suffix}.png"
            )

            if card_name and card_link:
                loaded_cardpool.append({"name": card_name, "link": card_link})

    return loaded_cardpool
