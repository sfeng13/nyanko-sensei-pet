"""Small offline games; independent of Qt, accounts and animation state."""
import hashlib
import json
import logging
import os
import random
import shutil
import tempfile
import time
from datetime import date
from pathlib import Path

GAMES = {
    "fortune": "今日运势", "food": "今天吃什么", "draw": "自己写签",
    "rps": "和老师猜拳", "guess": "猜数字", "coin": "抛硬币", "dice": "掷骰子",
}
FOODS = (
    "面条", "饺子", "盖浇饭", "炒饭", "麻辣烫", "米线", "馄饨", "寿司", "砂锅", "汉堡", "披萨", "家常菜",
    "鸭肉粿条", "小男当家", "面窝", "苕面窝", "蛋酒配热干面", "三鲜豆皮", "汽水包", "排骨藕汤",
    "藕丸子", "糯米丸子", "鱼丸子", "炸藕夹", "鱼糕", "粉蒸肉", "卤味", "藕带", "武昌鱼",
    "糊汤粉", "掺汤", "财鱼面", "米发糕", "矮子馅饼", "藕粉", "米酿",
)
DRAW_OPTIONS = ("工作", "写论文", "刷视频", "打游戏", "出去逛")


class GamePools:
    """Editable game content stored outside the replaceable installation."""

    def __init__(self, path=None):
        from nyanko_paths import user_data_dir
        self.path = Path(path) if path is not None else user_data_dir() / "games.json"
        self.values = {"food": "\n".join(FOODS), "draw": "\n".join(DRAW_OPTIONS)}
        self._document = {"version": 1, "pools": {}}
        self._corrupt = False
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(document, dict) or not isinstance(document.get("pools"), dict):
                raise ValueError("Invalid game pools document")
            self._document = document
            for key in self.values:
                value = document["pools"].get(key)
                if isinstance(value, str):
                    self.values[key] = value
        except FileNotFoundError:
            pass
        except (ValueError, OSError) as error:
            self._corrupt = True
            logging.getLogger(__name__).warning("Cannot load game options: %s", error)

    def update(self, key, text):
        if key not in self.values:
            raise ValueError("Unknown game pool")
        self.values[key] = text
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self._corrupt and self.path.exists():
            shutil.copy2(self.path, self.path.with_name(self.path.name + f".corrupt-{time.time_ns()}"))
            self._corrupt = False
        self._document["pools"].update(self.values)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                             prefix=self.path.name + ".", suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(self._document, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()


FORTUNES = (
    ("大大吉", "云开见日，心愿逢春。\n宜主动开口，忌把机会藏在草稿里。\n老师：这么好的签，团子要买双份！"),
    ("大大吉", "花开满枝，好事相随。\n宜试试惦记已久的小计划，忌只想不动。\n老师：今天的夸奖，本大人替你收下了。"),
    ("大大吉", "顺风入怀，惊喜叩门。\n宜分享喜悦，忌得意忘形。\n老师：烤鱿鱼最后一串，居然也留给你了！"),
    ("大吉", "春风送暖，前路渐明。\n宜解决一件拖延的小事，忌临门退缩。\n老师：做完再吃点心，味道都更好了。"),
    ("大吉", "积雨初晴，旧事有解。\n宜换个角度再试，忌太早说不行。\n老师：看吧，本大人早说你有两下子。"),
    ("大吉", "好意相逢，小愿可成。\n宜联系想念的人，忌把感谢憋在心里。\n老师：有人陪着吃饭，就是好日子。"),
    ("中吉", "缓步登阶，渐近山光。\n宜踏实做完手头事，忌一口气揽太多。\n老师：团子也得一口一口吃。"),
    ("中吉", "枝头有信，静候花开。\n宜给计划一点时间，忌催着所有事立刻有答案。\n老师：坐稳，好的点心还在蒸呢。"),
    ("中吉", "细水长流，积少成多。\n宜坚持一个小习惯，忌拿自己和别人赛跑。\n老师：今天比昨天多走一步就够了。"),
    ("小吉", "檐下微风，偶得清欢。\n宜留意身边的小惊喜，忌只盯着没做完的事。\n老师：多送了一颗丸子？这也是运气。"),
    ("小吉", "小路转弯，另有花香。\n宜尝试一点新鲜事，忌把日子过得太着急。\n老师：换家店，说不定有好吃的。"),
    ("小吉", "一灯虽小，也照归途。\n宜完成一件小事，忌嫌成果不够大。\n老师：收好桌面，就给你记上一功。"),
    ("吉", "人间有味，寻常也甜。\n宜好好吃饭，忌一边休息一边内疚。\n老师：吃饱了，才有力气做正事。"),
    ("吉", "同路相伴，话暖三分。\n宜认真听一句话，忌急着争个输赢。\n老师：分我半个团子，这事就好商量。"),
    ("吉", "窗明几净，心事渐轻。\n宜整理一个角落，忌被零碎事情牵着走。\n老师：给本大人留块晒太阳的地方。"),
    ("末吉", "迟来的春，也会开花。\n宜把准备做足，忌因为暂时没动静就放弃。\n老师：好吃的往往最后才端上桌。"),
    ("末吉", "月藏云后，光还在呢。\n宜先走眼前这一步，忌替明天提前烦恼。\n老师：先睡好，明天再和麻烦较劲。"),
    ("末吉", "慢火煮茶，滋味渐来。\n宜留一点耐心，忌来回修改已经选好的小事。\n老师：别掀锅盖了，团子还没熟！"),
    ("平", "风不催帆，日子自安。\n宜照常生活，忌非得找个大消息。\n老师：没有怪事，正好安心打盹。"),
    ("平", "一餐一觉，也算圆满。\n宜留一段空闲，忌把每一分钟都排满。\n老师：今日任务——晒太阳。"),
    ("平", "无波小池，也映晴空。\n宜按自己的节奏来，忌反复翻旧烦恼。\n老师：普通的一天，也值得一份点心。"),
    ("凶", "风来翻页，莫急落笔。\n宜发消息前再看一遍，忌气头上争辩。\n老师：少说两句，省下力气嚼团子。"),
    ("凶", "路有小石，慢些不绊。\n宜把东西放回原处，忌出门时手忙脚乱。\n老师：钥匙先找好，别又让本大人等。"),
    ("凶", "茶洒半杯，余香尚在。\n宜留点余地，忌为一件小失误责怪自己。\n老师：擦干净就好，下一杯照样喝。"),
    ("大凶", "逆风当歇，勿与风争。\n宜缩短待办清单，忌硬撑着证明什么。\n老师：今天先躲到被窝里攒力气。"),
    ("大凶", "忙中易错，慢即是快。\n宜保存文件、检查一遍，忌随手点错按钮。\n老师：本大人批准你少忙一点。"),
    ("大凶", "乱线成团，先解一结。\n宜一次处理一件事，忌把所有麻烦堆到一起。\n老师：烦恼没理顺，尾巴倒先打结了。"),
    ("大大凶", "零食见底，团子滚桌。\n宜给自己留口点心，忌空着肚子生闷气。\n老师：糟了！最后一口已经被我吃掉了。"),
    ("大大凶", "猫占软垫，杯里无茶。\n宜暂停一下再出发，忌跟小倒霉死磕。\n老师：座位我先占着，你去拿点心吧。"),
    ("大大凶", "计划跑偏，懒觉泡汤。\n宜把期待调小一点，忌让一天的小事毁掉心情。\n老师：签虽凶，本大人还在这里陪你。"),
)


def daily_fortune(day=None):
    day = day or date.today()
    index = int.from_bytes(hashlib.sha256(day.isoformat().encode()).digest()[:4], "big") % len(FORTUNES)
    title, text = FORTUNES[index]
    return f"{day:%m月%d日} · {title}\n{text}"


def random_fortune(day=None, previous=None, rng=random):
    day = day or date.today()
    pool = [f"{day:%m月%d日} · {title}\n{text}" for title, text in FORTUNES]
    return rng.choice([text for text in pool if text != previous])


def draw_option(text, rng=random):
    options = list(dict.fromkeys(line.strip() for line in text.splitlines() if line.strip()))
    if len(options) < 2:
        raise ValueError("至少写两个不同的选项，每行一个。")
    return rng.choice(options)


def play_rps(player, rng=random):
    choices = ("石头", "剪刀", "布")
    if player not in choices:
        raise ValueError("请选择石头、剪刀或布。")
    teacher = rng.choice(choices)
    difference = (choices.index(player) - choices.index(teacher)) % 3
    verdict = ("平手！再来一局？", "老师赢了！哼哼。", "你赢了！这次算你厉害。") [difference]
    return f"你：{player}　老师：{teacher}\n{verdict}"


class NumberGame:
    def __init__(self, rng=random):
        self.target = rng.randint(1, 100)
        self.attempts = 0
        self.finished = False

    def guess(self, number):
        if self.finished:
            return "这一局结束啦，点“新一局”再来。"
        if not 1 <= number <= 100:
            raise ValueError("请猜 1 到 100 之间的整数。")
        self.attempts += 1
        if number == self.target:
            self.finished = True
            return f"猜中了！答案是 {number}，你用了 {self.attempts} 次。"
        if self.attempts >= 7:
            self.finished = True
            return f"七次用完啦，老师藏的数字是 {self.target}。再试一次？"
        hint = "偏小，再大一点" if number < self.target else "偏大，再小一点"
        return f"{number}：{hint}。还剩 {7 - self.attempts} 次。"
