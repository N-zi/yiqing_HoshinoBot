import json
from sys import path_importer_cache
import hoshino
from hoshino import Service,priv
from hoshino import aiorequests
from hoshino.util import FreqLimiter
from PIL import Image,ImageDraw, ImageFont
import io
import base64


flmt = FreqLimiter(5)
url = "https://view.inews.qq.com/g2/getOnsInfo?name=disease_h5"  # 腾讯api

sv = Service(
    name = '疫情数据',  #功能名
    use_priv = priv.NORMAL, #使用权限   
    manage_priv = priv.ADMIN, #管理权限
    visible = True, #False隐藏
    enable_on_default = True, #是否默认启用
    )
    
    
# ============================================ #


async def get_yiqing_data(area: str) -> str:
    # 应该不会有人闲到写全称吧
    if area == "内蒙古自治区": area = "内蒙古"
    elif area == "宁夏回族自治区": area = "宁夏"
    elif area == "新疆维吾尔自治区": area = "新疆"
    elif area == "西藏自治区": area = "西藏"
    elif area == "广西壮族自治区": area = "广西"
    type_ = ""  # 标记是省还是市
    result = {}
    msg = ""
    raw_data = await aiorequests.get(url=url)
    raw_data = await raw_data.json()
    if raw_data['ret'] != 0:
        print('ret不为0，疑似有问题')
    data = json.loads(raw_data['data'])
    tree = data['areaTree']
    all_province = tree[0]['children']

    # 先最特殊情况
    if area == "中国":
        data.pop("areaTree")
        msg += f"中国（含港澳台）疫情：\n"
        msg += f"现存确诊{data['chinaTotal']['nowConfirm']}(+{data['chinaAdd']['confirm']})\n"
        try:
            msg += f"现存疑似{data['chinaTotal']['suspect']}(+{data['chinaAdd']['suspect']})\n"
        except:
            msg += "无法获取疑似病例数据\n"
        msg += f"累计确诊{data['chinaTotal']['confirm']}\n"
        msg += f"累计治愈{data['chinaTotal']['heal']}\n"
        msg += f"累计死亡{data['chinaTotal']['dead']}\n"
        return msg
    else:
        # 移除“市”
        if area[-1] == "市":
            area = area[0:-1]
        # 先找省
        if area[-1] == "省":
            for province in all_province:
                if province['name'] == area[0:-1]:
                    province.pop('children')
                    result = province
                    type_ = "(省)"
            # 针对指定为省份的查询
            pass
        else:
            # 不会优化，两个for嗯找，能跑就行
            for province in all_province:
                if province['name'] == area and "省" not in area:
                    # 没有写“省”字，但要找的确实是一个省
                    province.pop('children')
                    result = province
                    type_ = "(省)"
                    break
                for city in province['children']:
                    if city['name'] == area:
                        result = city
                        type_ = "(市)"
    msg += f"{result['name']}{type_}疫情：\n"
    msg += f"现存确诊：{result['total']['nowConfirm']}" + (f"(+{result['today']['confirm']})" if result['today']['confirm'] > 0 else "")
    msg += "\n"
    try:
        msg += f"现存疑似：{result['total']['suspect']}\n"
    except:
        msg += f"无法获取疑似病例数据\n"
    msg += f"累计确诊：{result['total']['confirm']}\n"
    try:
        msg += f"累计死亡：{result['total']['dead']} ({result['total']['deadRate']}%)\n"
    except:
        msg += f"累计死亡：{result['total']['dead']} ({(result['total']['dead']/result['total']['confirm']*100):.2f}%)\n"
    try:
        msg += f"累计治愈：{result['total']['heal']} ({result['total']['healRate']}%)\n"
    except:
        msg += f"累计治愈：{result['total']['heal']} ({(result['total']['heal']/result['total']['confirm']*100):.2f}%)\n"
    try:
        msg += f"风险等级：{result['total']['grade']}\n" if type_ == "(市)" else ""
    except:
        msg += "无法获取风险等级信息\n"
    msg += f"当前地区信息今日已更新\n最后更新时间：\n{data['lastUpdateTime']}" if result['today']['isUpdated'] else "！当前地区信息今日无更新"
    return msg



def image_draw(msg):

    img = Image.new("RGB",(200,200),(255,255,255))
    draw = ImageDraw.Draw(img)
    font1 = ImageFont.truetype('simhei.ttf', 16)
    draw.text((0, 0), msg, fill=(0, 0, 0), font=font1)
    b_io = io.BytesIO()
    img.save(b_io, format = "JPEG")
    base64_str = 'base64://' + base64.b64encode(b_io.getvalue()).decode()
    return base64_str

@sv.on_suffix("疫情")
@sv.on_prefix("疫情")
async def yiqing(bot,ev):
    #冷却器检查
    if not flmt.check(ev['user_id']):
        await bot.send(ev,f"查询冷却中，请{flmt.left_time(ev['user_id'])}秒后再试~",at_sender=True)
        return
    area = ev.message.extract_plain_text()
    try:
        msg = await get_yiqing_data(area)
        flmt.start_cd(ev['user_id'])
    except Exception as e:
        if str(e) == "'name'":
            msg = "无法查询该地区疫情"
        else:
            msg = f"查询{area}数据失败：{e}"
        flmt.start_cd(ev['user_id'],3)
    if len(msg)<30:
        await bot.send(ev,msg)
    else:
        pic = image_draw(msg)
        await bot.send(ev, f'[CQ:image,file={pic}]')

@sv.on_fullmatch('疫情帮助')
async def yiqing_help(bot,ev):
    help_msg = "输入xx[省市]疫情，获取xx地区的疫情信息。xx只可输入一级或二级行政区名。省代表一级行政区（包括直辖市、省、自治区、特别行政区），市代表地级行政区（包括地级市、地区、自治州、盟）"
    await bot.send(ev,help_msg)
