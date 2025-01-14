from collections import defaultdict
from typing import Optional

import discord
from discord import Message as DiscordMessage, app_commands
import logging
from src.base import Message, Conversation, ChannelConfig
from src.constants import (
    BOT_INVITE_URL,
    DISCORD_BOT_TOKEN,
    EXAMPLE_CONVOS,
    MAX_CHANNEL_MESSAGES,
    SECONDS_DELAY_RECEIVING_MSG,
    AVAILABLE_MODELS,
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
    CHANNEL_SETTINGS_FILE,
)
import asyncio
from src.utils import (
    logger,
    should_block,
    is_last_message_stale,
    discord_message_to_message,
)
from src import completion
from src.completion import generate_completion_response, process_response
from src.moderation import (
    moderate_message,
    send_moderation_blocked_message,
    send_moderation_flagged_message,
)
import os, json

logging.basicConfig(
    format="[%(asctime)s] [%(filename)s:%(lineno)d] %(message)s", level=logging.INFO
)

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)
channel_data = defaultdict()


@client.event
async def on_ready():
    logger.info(f"We have logged in as {client.user}. Invite URL: {BOT_INVITE_URL}")
    completion.MY_BOT_NAME = client.user.name
    completion.MY_BOT_EXAMPLE_CONVOS = []
    for c in EXAMPLE_CONVOS:
        messages = []
        for m in c.messages:
            if m.user == "Lenard":
                messages.append(Message(user=client.user.name, text=m.text))
            else:
                messages.append(m)
        completion.MY_BOT_EXAMPLE_CONVOS.append(Conversation(messages=messages))
        
    # load channel settings
    if os.path.exists(CHANNEL_SETTINGS_FILE):
        with open(CHANNEL_SETTINGS_FILE, "r") as f:
            saved_data = json.load(f)
            for channel_id_str, config_dict in saved_data.items():
                channel_data[int(channel_id_str)] = ChannelConfig(**config_dict)
    await tree.sync()


@tree.command(name="settings", description="Set settings for current channel")
@discord.app_commands.checks.has_permissions(send_messages=True)
@discord.app_commands.checks.has_permissions(view_channel=True)
@discord.app_commands.checks.bot_has_permissions(send_messages=True)
@discord.app_commands.checks.bot_has_permissions(view_channel=True)
@app_commands.describe(model="The model to use")
@app_commands.describe(
    temperature="Controls randomness. Higher values mean more randomness. Between 0 and 1"
)
@app_commands.describe(
    max_tokens="How many tokens the model should output at max for each message."
)
async def chat_command(
    int: discord.Interaction,
    model: Optional[AVAILABLE_MODELS],
    temperature: Optional[float],
    max_tokens: Optional[int],
):
    try:
        # block servers not in allow list
        if should_block(guild=int.guild, channel=int.channel):
            return

        user = int.user
        logger.info(f"settings command by {user}")

        # Check for valid temperature
        if temperature is not None and (temperature < 0 or temperature > 1):
            await int.response.send_message(
                f"You supplied an invalid temperature: {temperature}. Temperature must be between 0 and 1.",
                ephemeral=True,
            )
            return

        # Check for valid max_tokens
        if max_tokens is not None and (max_tokens < 1 or max_tokens > 4096):
            await int.response.send_message(
                f"You supplied an invalid max_tokens: {max_tokens}. Max tokens must be between 1 and 4096.",
                ephemeral=True,
            )
            return

        config = channel_data.setdefault(
            int.channel.id,
            ChannelConfig(model=DEFAULT_MODEL, temperature=DEFAULT_TEMPERATURE, max_tokens=DEFAULT_MAX_TOKENS)
        )

        if model is not None:
            config.model = model
        if temperature is not None:
            config.temperature = temperature
        if max_tokens is not None:
            config.max_tokens = max_tokens
    
        channel_data[int.channel.id] = config
        
        embed = discord.Embed(
            description=f"Settings for {int.channel.mention}",
            color=discord.Color.green(),
        )
        embed.add_field(name="model", value=config.model)
        embed.add_field(name="temperature", value=config.temperature, inline=True)
        embed.add_field(name="max_tokens", value=config.max_tokens, inline=True)

        await int.response.send_message(embed=embed)

    except Exception as e:
        logger.exception(e)
        await int.response.send_message(
            f"Failed to start chat {str(e)}", ephemeral=True
        )
        
    with open(CHANNEL_SETTINGS_FILE, "w") as f:
        json.dump({str(k): v.__dict__ for k, v in channel_data.items()}, f)


# calls for each message
@client.event
async def on_message(message: DiscordMessage):
    try:
        # block servers not in allow list
        if should_block(guild=message.guild, channel=message.channel):
            return

        # ignore messages from the bot
        if message.author == client.user:
            return

        channel = message.channel

        # moderate the message
        flagged_str, blocked_str = moderate_message(
            message=message.content, user=message.author
        )
        await send_moderation_blocked_message(
            guild=message.guild,
            user=message.author,
            blocked_str=blocked_str,
            message=message.content,
        )
        if len(blocked_str) > 0:
            try:
                await message.delete()
                await channel.send(
                    embed=discord.Embed(
                        description=f"❌ **{message.author}'s message has been deleted by moderation.**",
                        color=discord.Color.red(),
                    )
                )
                return
            except Exception as e:
                await channel.send(
                    embed=discord.Embed(
                        description=f"❌ **{message.author}'s message has been blocked by moderation but could not be deleted. Missing Manage Messages permission in this Channel.**",
                        color=discord.Color.red(),
                    )
                )
                return
        await send_moderation_flagged_message(
            guild=message.guild,
            user=message.author,
            flagged_str=flagged_str,
            message=message.content,
            url=message.jump_url,
        )
        if len(flagged_str) > 0:
            await channel.send(
                embed=discord.Embed(
                    description=f"⚠️ **{message.author}'s message has been flagged by moderation.**",
                    color=discord.Color.yellow(),
                )
            )

        # wait a bit in case user has more messages
        if SECONDS_DELAY_RECEIVING_MSG > 0:
            await asyncio.sleep(SECONDS_DELAY_RECEIVING_MSG)
            if is_last_message_stale(
                interaction_message=message,
                last_message=channel.last_message,
                bot_id=client.user.id,
            ):
                # there is another message, so ignore this one
                return

        logger.info(
            f"Message to process - {message.author}: {message.content[:50]} - {channel.name} {channel.jump_url}"
        )

        channel_messages = [
            discord_message_to_message(message)
            async for message in channel.history(limit=MAX_CHANNEL_MESSAGES)
        ]
        channel_messages = [x for x in channel_messages if x is not None]
        channel_messages.reverse()

        current_channel_data = channel_data.get(channel.id, ChannelConfig(
                model=DEFAULT_MODEL,
                max_tokens=DEFAULT_MAX_TOKENS,
                temperature=DEFAULT_TEMPERATURE,
            ))

        # generate the response
        async with channel.typing():
            response_data = await generate_completion_response(
                messages=channel_messages,
                user=message.author,
                channel_config=current_channel_data,
            )

        if is_last_message_stale(
            interaction_message=message,
            last_message=channel.last_message,
            bot_id=client.user.id,
        ):
            # there is another message and its not from us, so ignore this response
            return

        # send response
        await process_response(
            user=message.author, channel=channel, response_data=response_data
        )
    except Exception as e:
        logger.exception(e)


client.run(DISCORD_BOT_TOKEN)
