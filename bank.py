import discord
from config_loader import get_config, set_config

async def bank_message(msg, content):
    guild = msg.guild
    channel = msg.channel
    user = msg.author
    bank_channel = get_config(guild.id, 'bank_channel')

    # query channel
    if content == '채널':
        if bank_channel == None:
            await channel.send('채널이 설정되지 않았습니다.')
        else:
            await channel.send(f'현재 채널 : {bank_channel}')
    
    # set channel
    if content.startswith('채널 '):
        new_channel = content[len('채널 '):]
        if not (new_channel.startswith('<#') and new_channel.endswith('>')):
            await channel.send('잘못된 채널입니다.')
            return
        
        set_config(guild.id, 'bank_channel', new_channel)
        await channel.send(f'채널이 {new_channel}(으)로 설정되었습니다.')

    if bank_channel == None:
        return
    
    accounts = get_config(guild.id, 'bank_accounts')
    if accounts == None:
        accounts = {}
        set_config(guild.id, 'bank_accounts', accounts)

    # query balance
    if content == '잔고':
        balance = get_balance(guild.id, user.mention)
        await channel.send(f'{user.mention}님의 잔고 : {format(balance, ",")}원')

    # send money
    if content.startswith('송금'):
        pass

def get_balance(guild_id, user_mention):
    accounts = get_config(guild_id, 'bank_accounts')

    if accounts == None:
        accounts = {}
        set_config(guild_id, 'bank_accounts', accounts)

    if not user_mention in accounts:
        accounts[user_mention] = 100000
    return accounts[user_mention]

def set_balance(guild_id, user_mention, f):
    accounts = get_config(guild_id, 'bank_accounts')
    accounts[user_mention] = f(accounts[user_mention])
    set_config(guild_id, 'bank_accounts', accounts)