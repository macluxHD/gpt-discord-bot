# GPT Discord Bot

Discord bot written in Python that uses the [chat completions API](https://platform.openai.com/docs/api-reference/chat/create) to have conversations with [OpenAI models](https://platform.openai.com/docs/models), and the [moderations API](https://beta.openai.com/docs/api-reference/moderations) to filter the messages.

This bot uses the [OpenAI Python Library](https://github.com/openai/openai-python) and [discord.py](https://discordpy.readthedocs.io/).


# Features

- `/settings` sets inference settings for the current text channel. You can optionally also adjust the `temperature` and `max_tokens` parameters and using `model` choose one of the available models. If you do not specify any of these parameters, the bot will just show the settings for the current channel.
- The model will generate a reply for every user message in the whitelisted channels
- Up to 200 previous messages will be passed to the model for each request, so the model will remember previous messages in the thread this can be adjusted in `src/constants.py` with `MAX_CHANNEL_MESSAGES`
- you can customize the bot instructions by modifying `config.yaml`

# Setup

1. Copy `.env.example` to `.env` and start filling in the values as detailed below
1. Go to https://beta.openai.com/account/api-keys, create a new API key, and fill in `OPENAI_API_KEY`
1. Create your own Discord application at https://discord.com/developers/applications
1. In your application go to the Bot tab
    - Click "Reset Token" and fill in `DISCORD_BOT_TOKEN`
    - Disable "Public Bot" unless you want other people to be able to invite your bot to their servers
    - Enable "Message Content Intent" under "Privileged Gateway Intents"
1. Go to the OAuth2 tab, copy your "Client ID", and fill in `DISCORD_CLIENT_ID`
1. Install dependencies and run the bot
    ```
    pip install -r requirements.txt
    python -m src.main
    ```
    You should see an invite URL in the console. Copy and paste it into your browser to add the bot to your server.
    Note: make sure you are using Python 3.9+ (check with python --version)

# Optional configuration

1. If you want to whitelist specific servers, copy the ID the server you want to allow your bot to be used in by right clicking the server icon and clicking "Copy Server ID". Fill in `ALLOWED_SERVER_IDS`. If you want to allow multiple servers, separate the IDs by "," like `server_id_1,server_id_2`. If you want to allow all servers leave this field empty.
1. If you want to whitelist specific channels, copy the ID of the channel you want to allow your bot to be used in by right clicking the channel and clicking "Copy Channel ID". Fill in `ALLOWED_CHANNEL_IDS`. If you want to allow multiple channels, separate the IDs by "," like `channel_id_1,channel_id_2`. If you want to allow all channels leave this field empty.
1. If you want moderation messages, create and copy the channel id for each server that you want the moderation messages to send to in `SERVER_TO_MODERATION_CHANNEL`. This should be of the format: `server_id:channel_id,server_id_2:channel_id_2`. If you do not want moderation messages, leave this field empty.
1. If you want to change the personality of the bot, go to `config.yaml` and edit the instructions
1. If you want to change the moderation settings for which messages get flagged or blocked, edit the values in `src/constants.py`. A higher value means less chance of it triggering, with 1.0 being no moderation at all for that category.

# FAQ

> Why isn't my bot responding to commands?

Ensure that the channels your bots have access to allow the bot to have these permissions.
- Send Messages
- Manage Messages (only for moderation to delete blocked messages)
- Read Message History
- Use Application Commands
