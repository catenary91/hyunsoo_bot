import random, itertools, functools
import discord
from config_loader import save_config, set_config, get_config
from card_image_loader import Card, card_list_to_file, make_card
from bank import get_balance, set_balance

image_channel = None
def set_image_channel(channel):
    global image_channel
    image_channel = channel

SHAPE_LABEL = ['스', '다', '하', '클']
SHAPES = ['S', 'D', 'H', 'C']
NUMBERS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
field_image_url = None

# return (score, score2, info)
def get_score_info(card_list):
    def is_straight(cards):
        cards2 = sorted(cards, key=lambda c:c.number_index)
        g = cards[0].number_index
        for i, c in enumerate(cards2[1:]):
            if i+g != c.number_index:
                return False
        return True

    cards = card_list.copy()

    # 플러쉬 검사
    shape_count = [0, 0, 0, 0]
    for card in cards:
        shape_count[card.shape_index] += 1
    flush = max(shape_count) >= 5
    
    # 1. 로티플
    if flush:
        flush_shape_index = shape_count.index(max(shape_count))
        if all([make_card(flush_shape_index, NUMBERS.index(n)) in cards for n in ['10', 'J', 'Q', 'K', 'A']]):
            return (10, 0, '로얄 스트레이트 플러쉬', [])

    # 2. 스트레이트 플러쉬
    if flush:
        flush_shape_index = shape_count.index(max(shape_count))
        flush_cards = [card for card in cards if card.shape_index==flush_shape_index]

        for sub_cards in itertools.combinations(flush_cards, 5):
            if is_straight(sub_cards):
                return (9, 0, '스트레이트 플러쉬', [])
    
    # 3. 포카드
    number_count = [0 for _ in range(len(NUMBERS))]
    for card in cards:
        number_count[card.number_index] += 1
    if max(number_count) == 4:
        return (8, number_count.index(4), '포카드', [])
    
    # 4. 풀하우스
    if number_count.count(3)>0 and number_count.count(2)>0:
        number_3 = number_count.index(3)
        number_2 = max([i for i, n in enumerate(number_count) if n==2])
        return (7, number_3 * 100 + number_2, '풀하우스', [])

    # 5. 플러쉬
    if flush:
        flush_shape_index = shape_count.index(max(shape_count))
        flush_cards = [card for card in cards if card.shape_index==flush_shape_index]
        info = [c.number_index for c in sorted(flush_cards, key=lambda c:c.number_index, reverse=True)]
        return (6, info, '플러쉬', [])
    
    # 6. 스트레이트
    max_straight = [0, 0, 0, 0, 0]
    for sub_cards in itertools.combinations(cards, 5):
        sorted_sub_cards = sorted(sub_cards, key=lambda c:c.number_index)
        if is_straight(sorted_sub_cards):
            max_straight = max(max_straight, [c.number_index for c in reversed(sorted_sub_cards)])
    if max_straight != [0, 0, 0, 0, 0]:
        return (5, max_straight, '스트레이트', [])
    
    # 7. 트리플
    if number_count.count(3)>0:
        number_3 = max([i for i, n in enumerate(number_count) if n==3])
        return (4, number_3, '트리플', [])
    
    # 8. 투페어
    if number_count.count(2)>1:
        number_2s = sorted([i for i, n in enumerate(number_count) if n==2], reverse=True)[:2]
        return (3, number_2s, '투페어', [])
    
    # 9. 원페어
    if number_count.count(2) == 1:
        number_2 = number_count.index(2)
        return (2, number_2, '원페어', [])
    
    # 10. 하이카드
    high_cards = sorted(cards, key=lambda c:c.number_index, reverse=True)[:5]
    return (1, [c.number_index for c in high_cards], '하이카드', [])


class PokerGame():
    def __init__(self, guild_id, recruiting, channel):
        self.recruiting = recruiting
        self.guild_id = guild_id
        self.running = False
        
        self.player_list = []
        self.valid_players = []
        self.current_player = 0
        self.betting_list = {}
        self.total_betting = 0
        self.die_list = {}

        self.check_list = []
        
        self.last_raise = None
        
        self.deck = [make_card(s, n) for s in range(len(SHAPES)) for n in range(len(NUMBERS))]
        random.shuffle(self.deck)
        self.player_card = {}
        self.field = []

        self.embed_msg = None
        self.thread = None
        self.poker_channel = channel
        
    def add_player(self, player):
        if player in self.player_list:
            return False
        else:
            self.player_list.append(player)
            self.last_raise = self.player_list[0]
            return True

    async def start(self, msg):
        self.recruiting = False
        self.running = True

        await self.give_card()
        self.do_default_betting()

        await self.update_embed(False)
        await self.send_next_turn_msg()

    def get_balances(self):
        balance_list = [f'{p.display_name}  :  {format(get_balance(self.guild_id, p.mention), ",")}원' for p in self.player_list]
        return '\n'.join(balance_list)
    
    def get_bettings(self):
        betting_list = []
        for i, p in enumerate(self.player_list):
            info = f'{p.display_name}  :  {format(self.betting_list[p.mention], ",")}원'
            if self.die_list[p.mention]:
                info += ' (다이)'
            elif get_balance(self.guild_id, p.mention) == 0:
                info += ' (올인)'
            if i == self.current_player:
                info += '  <-- 현재 차례'
            betting_list.append(info)
        return '\n'.join(betting_list)
    
    def do_default_betting(self):
        for p in self.player_list:
            get_balance(self.guild_id, p.mention) # 잔고 설정이 안돼있으면 100,000원으로 초기화
            self.betting_list[p.mention] = 0
            self.do_betting(p, 100)
            self.die_list[p.mention] = False

    async def give_card(self):
        for p in self.player_list:
            self.player_card[p.mention] = [self.deck.pop(), self.deck.pop()]
            if p.dm_channel == None:
                channel = await p.create_dm()    
            else:
                channel = p.dm_channel
            await channel.send('당신의 패', file=card_list_to_file(self.player_card[p.mention]))
    

    def set_embed_msg(self, embed_msg):
        self.embed_msg = embed_msg
    def set_thread(self, thread):
        self.thread = thread
    async def update_embed(self, update_img):
        global field_image_url

        embed = discord.Embed(title='포커 (텍사스 홀덤)')
        embed.add_field(name='잔고', value=self.get_balances(), inline=False)
        embed.add_field(name=f'베팅 금액 (총 {format(self.total_betting, ",")}원)', value=self.get_bettings(), inline=False)
        embed.add_field(name='베팅 종류', value='''
        "!체크" : 베팅을 하지 않고 자신의 턴을 넘깁니다.
        "!레이즈 <금액>" : <금액>만큼 더 베팅합니다.
        "!콜" : 상대방이 추가로 베팅한 만큼의 금액을 베팅합니다.
        "!올인" : 자신의 전재산을 베팅합니다.
        "!다이" : 더 이상 베팅을 하지 않고 게임을 포기합니다.
        ''', inline=False)

        if update_img and self.field != []:
            image_file = card_list_to_file(self.field)
            image_msg = await image_channel.send(file=image_file)
            embed.add_field(name='필드', value='', inline=False)
            field_image_url = image_msg.attachments[0].url
        if self.field != []:
            embed.set_image(url=field_image_url)
        
        self.embed_msg = await self.embed_msg.edit(embed=embed)

    async def send_next_turn_msg(self):
        await self.thread.send(f'{self.player_list[self.current_player].mention}님의 베팅 차례입니다.')

    def can_do_betting(self, player):
        return not self.die_list[player.mention] and get_balance(self.guild_id, player.mention)

    async def next_turn(self, msg):

        
        # 더 베팅할 수 있는 사람
        valid_players = [p for p in self.player_list if self.can_do_betting(p)]
        
        # 더 이상 베팅할 필요가 없음
        if len(valid_players) <= 1:
            while len(self.field) != 5:
                self.field.append(self.deck.pop())
            await self.view_result()
            return

        # 베팅이 끝나지 않음 (추가 레이즈 존재) or 현재 플레이어가 체크
        if any([self.betting_list[p.mention] != self.betting_list[valid_players[0].mention] for p in valid_players]) or self.player_list[self.current_player] in self.check_list:
            next_player_index = self.current_player
            while True:
                next_player_index = (next_player_index + 1) % len(self.player_list)
                if next_player_index == self.current_player or self.player_list[next_player_index] in self.check_list:
                    # 더 이상 베팅할 수 있는 사람이 없음
                    break

                next_player = self.player_list[next_player_index]
                if self.can_do_betting(next_player):
                    self.current_player = next_player_index
                    await self.update_embed(False)
                    await self.send_next_turn_msg()
                    return
        
        # 한 차례 베팅이 끝남
        self.check_list = []

        # 필드에 카드가 5장이면 게임종료
        if len(self.field) == 5:
            await self.view_result()
            return
        
        
        if len(self.field) == 0:
            # 첫 베팅 이후 카드 3장 오픈
            self.field.append(self.deck.pop())
            self.field.append(self.deck.pop())
            self.field.append(self.deck.pop())
        else:
            # 카드 1장 오픈
            self.field.append(self.deck.pop())
        
        
        if self.can_do_betting(self.last_raise):
            self.current_player = [i for i, p in enumerate(self.player_list) if p == self.last_raise][0]
        else:
            next_player_index = self.current_player
            while True:
                next_player_index = (next_player_index + 1) % len(self.player_list)
                next_player = self.player_list[next_player_index]
                if self.can_do_betting(next_player):
                    self.current_player = next_player_index
                    break

        await self.update_embed(True)
        await self.send_next_turn_msg()
    
    def do_betting(self, player, money): # do not check validity
        self.total_betting += money
        self.betting_list[player.mention] += money
        set_balance(self.guild_id, player.mention, lambda x:x-money)

    async def view_result(self):
        await self.update_embed(False)
        self.running = False
        def compare_score(s1, s2):
            if s1[0]<s2[0]:
                return -1
            elif s1[0]>s2[0]:
                return 1
            else:
                if s1[1]<s2[1]:
                    return -1
                elif s1[1]>s2[1]:
                    return 1
                else:
                    return 0

        results = [get_score_info(cs + self.field) + (mention,) for mention, cs in self.player_card.items()]
        results.sort(key=functools.cmp_to_key(compare_score), reverse=True )

        winner_list = [results[0]]
        for result in results:
            info = result[2]
            cards = result[3]
            player = self.mention_to_user(result[4])
            await self.poker_channel.send(f'{player.display_name} : {info}', file=card_list_to_file(self.field + self.player_card[player.mention]))

            # winner_list에 다이 유저는 제외
            if compare_score(result, winner_list[0])==0 and not result in winner_list and not self.die_list[player]:
                winner_list.append(result)

        winner_list = [self.mention_to_user(winner[3]) for winner in winner_list]

        prize = int(self.total_betting / len(winner_list))
        for winner in winner_list:
            set_balance(self.guild_id, winner.mention, lambda x:x+prize)

        winner_embed = discord.Embed(title='게임 종료')
        winner_embed.add_field(name='우승자', value=', '.join([winner.mention for winner in winner_list]), inline=False)
        winner_embed.add_field(name='현재 잔고', value='\n'.join([f'{p.display_name} : {get_balance(self.guild_id, p.mention)}' for p in self.player_list]), inline=False)
        await self.poker_channel.send(embed=winner_embed)

        save_config()

    def mention_to_user(self, mention):
        return [p for p in self.player_list if p.mention == mention][0]
# key : guild_id
game_list = {}

poker_thumbnail = discord.File("card\\thumbnail.png")

last_user_msg = None
last_bot_msg = None

async def send_disposable_msg(msg, error_msg):
    global last_user_msg, last_bot_msg
    if last_user_msg != None:
        await last_user_msg.delete()
    if last_bot_msg != None:
        await last_bot_msg.delete()
    last_user_msg = msg
    last_bot_msg = await msg.channel.send(error_msg)

async def poker_message(msg, content):
    if content.startswith('getvalue '):
        cards = [Card(s) for s in content[len('getvalue '):].split()]
        await msg.channel.send(str(get_score_info(cards)))

    guild = msg.guild
    channel = msg.channel
    poker_channel = get_config(guild.id, 'poker_channel')

    if content == '채널':
        if poker_channel == None:
            await channel.send('채널이 설정되지 않았습니다.')
        else:
            await channel.send(f'현재 채널 : {poker_channel}')

    if content.startswith('채널 '):
        new_channel = content[len('채널 '):]
        
        if not (new_channel.startswith('<#') and new_channel.endswith('>')):
            await msg.reply('잘못된 채널입니다.')
            return
        
        set_config(guild.id, 'poker_channel', new_channel)
        await channel.send(f'채널이 {new_channel}(으)로 설정되었습니다.')

    if poker_channel == None:
        return
    
    if channel.mention == poker_channel:
        await recruit_message(msg, content)
    elif guild.id in game_list and game_list[guild.id] != None and channel == game_list[guild.id].thread:
        await play_message(msg, content)


async def recruit_message(msg, content):

    guild = msg.guild
    channel = msg.channel

    if not guild.id in game_list:
        game_list[guild.id] = PokerGame(guild.id, False, msg.channel)
    game = game_list[guild.id]

    # game command from now on

    if content == '모집':
        if game.recruiting:
            await send_disposable_msg('이미 모집 중입니다.')
        elif game.running:
            await send_disposable_msg('게임이 이미 진행 중입니다.')
        else:
            for t in channel.threads:
                await t.delete()
            await channel.purge(limit=100)

            embed = discord.Embed(title='포커 (텍사스 홀덤)', description=f'포커 게임을 모집합니다.\n스레드에서 참가해보세요!')
            embed.set_image(url='https://cdn.discordapp.com/attachments/1147936630901059657/1148174158149210202/thumbnail.png')
            embed_msg = await channel.send(embed=embed)

            thread = await embed_msg.create_thread(name='포커 명령어')

            embed.description = f'포커 게임을 모집합니다. : {thread.mention} 스레드에서 참가해보세요!'
            embed_msg = await embed_msg.edit(embed=embed)

            game_list[guild.id] = PokerGame(guild.id, True, msg.channel)
            game = game_list[guild.id]

            game.set_embed_msg(embed_msg)
            game.set_thread(thread)

            game.add_player(msg.author)

            desc_embed = discord.Embed(title='포커 명령어 목록')
            desc_embed.add_field(name='!참가', value='참가비 100원을 지불하여 포커 게임에 참가합니다.', inline=False)
            desc_embed.add_field(name='!시작', value='포커 게임을 시작합니다.', inline=False)
            await thread.send(embed=desc_embed)

            await thread.send(f'{msg.author.mention}님이 게임에 참여하였습니다.')
        return
    
    if content == '취소' and game.recruiting:
        game.recruiting = False
        
async def delete_poker_msg(msg, content, prefix):
    if msg.author.bot:
        return
    if (not content.startswith(prefix + '포커 ')) and msg.channel.mention == get_config(msg.guild.id, 'poker_channel'):
        await msg.delete()
        
    

async def play_message(msg, content):
    global game_list

    channel = msg.channel
    guild = msg.guild
    if not guild.id in game_list:
        return

    game = game_list[guild.id]
    if game.thread == None or game.thread.id != msg.channel.id:
        return

    if content == '참가':
        if not game.recruiting:
            await msg.reply(msg, '현재 모집 중이 아닙니다.')
        elif game.running:
            await msg.reply(msg, '게임이 이미 진행 중입니다.')
        else:
            if not game.add_player(msg.author):
                await msg.reply('게임에 이미 참가하였습니다.')
            elif get_balance(guild.id, msg.author.mention) <= 100:
                await msg.reply('잔고가 100원 이하이면 참가할 수 없습니다.')
                return
            else:
                await channel.send(f'{msg.author.mention}님이 게임에 참가하였습니다.')

    if content == '시작':
        if game.running:
            await msg.reply('게임이 이미 진행 중입니다.')
        elif not game.recruiting:
            await msg.reply('게임 모집 중이 아닙니다.')
        elif game.player_list == [] or msg.author != game.player_list[0]:
            await msg.reply('주최자만 게임을 시작할 수 있습니다.')
        elif len(game.player_list) == 1:
            await msg.reply('혼자서는 게임을 시작할 수 없습니다.')
        else: 
            # 게임 시작
            await game.start(msg)
 

    # 지금부터 베팅 명령어
    
    # 현재 차례가 아니면 무시
    if msg.author != game.player_list[game.current_player]:
        return

    player = msg.author
    cur_betting= game.betting_list[player.mention]
    max_betting = max(game.betting_list.values())
    balance = get_balance(guild.id, player.mention)
    
    # 남은 잔고가 없으면 사이드 베팅 or 올인
    if balance == 0:
        await game.next_turn(msg)


    if content == '체크':
        # print('check')
        if cur_betting < max_betting:
            await msg.reply(f'{format(max_betting, ",")}원 이상이 되게 반드시 베팅해야 합니다. (콜 또는 레이즈)')
        elif cur_betting == max_betting:
            game.check_list.append(player)
            await game.next_turn(msg)

    if content == '레이즈':
        await msg.reply('"!레이즈 <금액>"으로 입력해주세요.')

    if content == '올인':
        # 레이즈로 변환
        content = f'레이즈 {balance}'

    if content == '콜':
        if cur_betting == max_betting:
            await msg.reply(f'추가로 베팅한 사람이 없습니다. 턴을 넘기시려면 "!체크"를 입력하세요.')
        elif cur_betting < max_betting:
            # max_betting - current_betting 만큼 추가 베팅
            inc_betting = max_betting - cur_betting

            if balance < inc_betting:
                await msg.reply(f'콜을 위한 잔고가 부족합니다. 게임을 계속하시려면 "!올인"을 입력하여 베팅하세요.')
                return
            
            game.do_betting(player, inc_betting)
            await channel.send(f'{player.mention}님이 콜을 외쳤습니다.')
            await game.next_turn(msg)

    if content.startswith('레이즈 '):
        try:
            inc_betting = int(content[len('레이즈 '):])
        except:
            await msg.reply('금액 입력이 잘못되었습니다.')
            return

        if balance > inc_betting and cur_betting + inc_betting <= max_betting:
            await msg.reply(f'{format(max_betting - cur_betting, ",")}원 초과의 금액만 추가로 베팅할 수 있습니다.')
            return

        if balance < inc_betting:
            await msg.reply(f'잔고가 부족합니다')
            return

        await channel.send(f'{player.mention}님이 {format(inc_betting, ",")}원을 추가로 베팅하였습니다.')
        game.do_betting(player, inc_betting)
        if max(game.betting_list.values()) > max_betting:
            game.last_raise = player
        await game.next_turn(msg)


    if content == '다이':
        await channel.send(f'{player.mention}님이 다이를 외쳤습니다.')
        game.die_list[player.mention] = True
        await game.next_turn(msg)