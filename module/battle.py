import math
import random

import discord
from discord.ext import commands as c

from module import db, item, monsters, status, str_calc

MONSTER_NUM = 50


class Battle(c.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def into_battle(self, user_id, channel_id):
        error_message = ""
        player_level = status.get_player_level(user_id)
        in_battle = db.player.hp.get(user_id)
        if not in_battle:
            player_hp = player_level * 5 + 50  # player_max_hp
            db.player.hp.set(user_id, channel_id, player_hp)
            return player_hp, error_message
        in_battle_channel_id = in_battle[0]
        battle_channel = self.bot.get_channel(in_battle_channel_id)
        if not battle_channel:  # if deleted the battle_channel
            player_hp = player_level * 5 + 50
            db.channel.not_found(in_battle_channel_id, channel_id, user_id, player_hp)
            return player_hp, error_message
        player_hp = in_battle[1]
        if in_battle_channel_id != channel_id:
            error_message = f"<@{user_id}>は'{battle_channel.guild.name}の{battle_channel.mention}'で既に戦闘中だ。"
        elif player_hp == 0:
            error_message = "<@{}>はもうやられている！（戦いをやり直すには「{}reset」だ）".format(user_id, db.prefix(self.bot.get_channel(channel_id).guild).get())
        return player_hp, error_message

    async def effect(self, ctx, monster):
        text = ["<@{}>は{}の毒ダメージを受けた".format(*i) for i in db.player.effect.poison.progress(ctx.channel.id) if i]
        if random.random() < monster["effect"].get("poison", [0])[0]:
            if db.player.effect.poison.add(ctx.author.id, ctx.channel.id, monster["effect"].get("poison", [5]*3)[2]):
                text += [f"{ctx.author.name}は毒の効果を受けてしまった！"]
        if text:
            return "\n"+"\n".join(text)
        return ""


def get_boss(ctx):
    channel_status = db.boss_status.get_st(ctx.channel.id)
    if not channel_status:
        boss_lv = 1
        monster = monsters.get(boss_lv)
        monster[1]["HP"] = monster[1]["HP"].replace("boss_level", str(boss_lv))
        db.boss_status.set_st(ctx, monster[0], boss_lv, str_calc.calc(monster[1]["HP"]))
        channel_status = [boss_lv, str_calc.calc(monster[1]["HP"]), monster[0]]
    return channel_status


def get_player_attack(player_level, boss_level, boss_id, rand):
    boss = monsters.get(boss_level, boss_id)
    if rand < boss[1]["Evasion rate"]:
        player_attack = 0
    elif boss_level % MONSTER_NUM in [3, 11, 17, 32, 41]:
        plus = rand / 3 + 0.5 if rand < 0.96 else 3
        player_attack = int(player_level * plus + 10)
    elif boss_level % 5 == 0:
        plus = rand / 2 + 0.8 if rand < 0.96 else 3
        player_attack = int(player_level * plus + 10)
    else:
        plus = rand / 2 + 1 if rand < 0.96 else 3
        player_attack = int(player_level * plus + 10)
    return player_attack


def get_attack_message(user_id, player_attack, monster_name, rand):
    if player_attack == 0:
        return "<@{}>の攻撃！{}にかわされてしまった...！！".format(user_id, monster_name, )
    elif rand == 2:
        return "<@{}>の特殊魔法！{}に`{}`のダメージを与えた！".format(user_id, monster_name, player_attack)
    else:
        kaishin = "会心の一撃！" if rand > 0.96 else ""
        return "<@{}>の攻撃！{}{}に`{}`のダメージを与えた！".format(user_id, kaishin, monster_name, player_attack)


def get_boss_attack(ctx):
    boss_lv, _, boss_id = db.boss_status.get_st(ctx.channel.id)
    monster = monsters.get(boss_lv, boss_id)[1]
    monster["ATK"] = monster["ATK"].replace("boss_level", str(boss_lv))
    return str_calc.calc(monster["ATK"])


def boss_attack_process(ctx, player_hp, player_level, monster_name):
    boss_attack = get_boss_attack(ctx)
    player_hp = player_hp - boss_attack
    user_id = ctx.author.id
    if boss_attack == 0:
        return "{0}の攻撃！<@{1}>は華麗にかわした！\n - <@{1}>のHP:`{2}`/{3}".format(
            monster_name, ctx.author.id, player_hp, player_level * 5 + 50)
    elif player_hp <= 0:
        db.player.hp.update(0, user_id)
        return "{0}の攻撃！<@{1}>は`{2}`のダメージを受けた。\n - <@{1}>のHP:`0`/{3}\n<@{1}>はやられてしまった。。。".format(
            monster_name, ctx.author.id, boss_attack, player_level * 5 + 50)
    else:
        db.player.hp.update(player_hp, user_id,)
        return "{0}の攻撃！<@{1}>は`{2}`のダメージを受けた。\n - <@{1}>のHP:`{3}`/{4}".format(
            monster_name, ctx.author.id, boss_attack, player_hp, player_level * 5 + 50)


def win_process(channel_id, boss_level, monster_name):
    battle_members = [m for m in
                      db.channel.all_player(channel_id)]
    level_up_comments = []
    members = ""
    fire_members = ""
    elixir_members = ""
    pray_members = ""
    boss_lv, _, boss_id = db.boss_status.get_st(channel_id)
    monster = monsters.get(boss_lv, boss_id)[1]
    monster["exp"] = monster["exp"].replace("boss_level", str(boss_lv))
    exp = str_calc.calc(monster["exp"])
    for battle_member in battle_members:
        member_id = battle_member[0]
        level_up_comments.append(status.experiment(member_id, exp))
        members += "<@{}> ".format(member_id)
        p = min(0.02 * boss_level * boss_level / db.player.experience.get(member_id), 0.1)
        if boss_level % 10 == 0 and random.random() < p:
            elixir_members += "<@{}> ".format(member_id)
            item.obtain_an_item(member_id, 1)
        if random.random() < p:
            fire_members += "<@{}> ".format(member_id)
            item.obtain_an_item(member_id, 2)
        if random.random() < p * 2:
            pray_members += "<@{}> ".format(member_id)
            item.obtain_an_item(member_id, 3)
    if fire_members:
        fire_members += "は`ファイアボールの書`を手に入れた！"
    if elixir_members:
        elixir_members += "は`エリクサー`を手に入れた！"
    if pray_members:
        pray_members += "は`祈りの書`を手に入れた！"
    level_up_comment = "\n".join([c for c in level_up_comments if c])
    item_get = "\n".join(c for c in [elixir_members, fire_members, pray_members] if c)
    msg="{0}を倒した！\n\n{1}は`{2}`の経験値を得た。\n{3}\n{4}".format(monster_name, members, exp, level_up_comment, item_get)
    return ("勝利メッセージが2000文字を超えたので表示できません" if len(msg)>2000 else msg)


async def reset_battle(ctx, level_up=False):
    db.channel.end_battle(ctx.channel.id, level_up)
    boss_lv, boss_hp, boss_id = get_boss(ctx)
    from module import monsters
    monster = monsters.get(boss_lv, boss_id)
    boss_lv += level_up
    monster = monsters.get(boss_lv, None if (monster[1].get("canReset") == "True" or level_up) else boss_id)
    from module.str_calc import calc
    monster[1]["HP"] = monster[1]["HP"].replace("boss_level", str(boss_lv))
    db.boss_status.set_st(ctx, monster[0], boss_lv,  calc(monster[1]["HP"]))
    em = discord.Embed(title="{}が待ち構えている...！\nLv.{}  HP:{}".
                       format(monster[1]["name"], boss_lv, calc(monster[1]["HP"])))
    em.set_image(url=f"{db.CONFIG_ROOT}Discord/FFM/img/{monster[1].get('img','404.png')}")
    await ctx.send(embed=em)
