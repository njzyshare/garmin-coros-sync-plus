"""临时：本地登录佳明，保存 .garth token 到 db/garth_tokens/"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from garmin.garmin_client import GarminClient

email = '18521567505'
password = 'Wg44269803'

print('正在尝试登录佳明中国区...')
gc = GarminClient(email, password, 'CN', 50)
try:
    acts = gc.getAllActivities()
    print(f'\n登录成功！获取到 {len(acts)} 条活动')
    for act in acts[:3]:
        aid = act.get('activityId')
        st = act.get('startTimeGMT', '') or ''
        name = act.get('activityName', '?')
        print(f'  {aid} "{name}" {st}')
    
    # 检查 token 文件是否已保存
    token_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'db', 'garth_tokens', 'garth_tokens.json'
    )
    if os.path.exists(token_path):
        print(f'\n✅ token 已保存到: {token_path} ({os.path.getsize(token_path)} bytes)')
    else:
        print(f'\n⚠️ token 文件未找到: {token_path}')
    
except Exception as e:
    print(f'\n登录异常: {e}')
    if 'MFA' in str(e):
        print('触发了 MFA，需要输入验证码。请重新运行并等待 MFA code: 提示后输入验证码')
    import traceback
    traceback.print_exc()

finally:
    input('\n按回车键退出...')
