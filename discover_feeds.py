import logging

from dateutil import parser
from datetime import datetime

from common import psapi
from common import helpers

podcasts_cfg_file = "podcasts.json"

inactive_days_limit = 30
ignore_days_limit = 365
title_prefix = "De 10 siste fra "

ignored_categories = []

def check_if_podcast_active(today, episodes):
    active = False
    obsolete = False
    for episode in episodes:
        episode_date = episode["date"]
        days_passed = ((today.timestamp() - parser.parse(episode_date).timestamp()) / 86400)
        if days_passed < inactive_days_limit:
            logging.debug(f"Podcast is active (episode age: {days_passed}d)")
            active = True
        if not active and (days_passed > ignore_days_limit):
            obsolete = True

    return {
        "active": active,
        "obsolete": obsolete
    }

def update_podcasts_config(configured, discovered):
    updated_c = 0
    added_c = 0

    for podcast_k, podcast in discovered.items():
        exists = False
        exists_i = None
        for i, c in enumerate(configured):
            if c['id'] == podcast['seriesId']:
                exists = True
                exists_i = i

        if exists and ("ignore" in configured[exists_i] and configured[exists_i]['ignore']):
            logging.debug(f"Ignoring podcast {podcast['seriesId']}")
            continue

        metadata = psapi.get_podcast_metadata(podcast['seriesId'])

        if "category" in metadata['series'] and metadata['series']['category']['id'] in ignored_categories:
            logging.debug(f"Podcast {podcast['seriesId']} is in ignored category {metadata['series']['category']['id']}")
            continue

        latest_season = None
        season = None

        if metadata['seriesType'] == "umbrella":
            latest_season = metadata["_links"]["seasons"][0]["name"]
            season = "LATEST_SEASON"

        episodes = psapi.get_podcast_episodes(podcast['seriesId'], latest_season)
        
        today = datetime.now()
        
        active = check_if_podcast_active(today, episodes)

        logging.debug(f"Latest season: {latest_season}, episodes found: {len(episodes)}")

        new_feed = {
            "id": podcast['seriesId'],
            "title": f"{title_prefix}{podcast['title']}",
            "season": season,
            "enabled": active['active']
        }

        if active['obsolete']:
            logging.warning(f"Podcast {podcast['title']} is considered obsolete and will be ignored in the future")
            new_feed["ignore"] = True
            new_feed["hidden"] = True

        if exists and (configured[exists_i]['enabled'] != new_feed['enabled'] or configured[exists_i]['season'] != new_feed['season']):
            logging.info(f"Updating existing podcast {podcast['seriesId']} (i: {exists_i})")
            configured[exists_i] = new_feed
            updated_c+=1

        if not exists:
            logging.info(f"Appending new podcast {podcast['seriesId']}")
            configured.append(new_feed)
            added_c+=1

    logging.info(f"Added {added_c} new podcast feed(s), {updated_c} existing feed(s) were updated")
    return configured

if __name__ == '__main__':
    helpers.init()

    configured = helpers.get_podcasts_config(podcasts_cfg_file)
    discovered = psapi.get_all_podcasts()
    updated = update_podcasts_config(configured, discovered)

    updated_sorted = sorted(updated, key=lambda d: d['id']) 
    helpers.write_podcasts_config(podcasts_cfg_file, updated_sorted)

    logging.info("Done")
