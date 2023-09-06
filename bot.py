import discord

from config_loader import get_config, set_config
from poker import play_message, poker_message, delete_poker_msg
from bank import bank_message

class Bot():
    def __init__(self, guild):
        self.guild_id = guild.id
        self.prefix = get_config(guild.id, 'prefix')

        # default prefix is '!'
        if self.prefix == None:
            self.prefix = '!'
            set_config(guild.id, 'prefix', '!')
            set_config(guild.id, 'name', guild.name)

    def set_prefix(self, prefix):
        self.prefix = prefix
        set_config(self.guild.id, 'prefix', prefix)

    async def on_message(self, msg):
        content = msg.content
        
        # 포커 채널에서의 유저 메시지는 삭제 (prefix가 없어도)
        await delete_poker_msg(msg, content, self.prefix)

        # prefix가 없으면 반응하지 않음
        if not content.startswith(self.prefix):
            return
        content = content[len(self.prefix):]

        # 아래부터는 prefix가 필요한 명령어

        # 은행 명령어
        if content.startswith('은행 '):
            await bank_message(msg, content[len('은행 '):])

        # 포커 명령어
        if content.startswith('포커 '):
            await poker_message(msg, content[len('포커 '):])

        # 포커 스레드에서의 명령어는 prefix만으로 인식
        await play_message(msg, content)


        if content.startswith('정리 '):
            num = int(content[len('정리 '):])
            await msg.channel.purge(limit=num)

        if content == 'test':
            await msg.channel.send("test file", file=discord.File('card\\thumbnail.png'), suppress_embeds=True)
        