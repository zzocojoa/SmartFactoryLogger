import configparser
import sys

config_content = """[SYSTEM]
devicename = Line_1_Final
intervalsec = 0.2

[EXTRUDER]
ip = 192.168.10.10
port = 12289

[SPOT]
ip = 10.1.10.50
refreshinterval = 3.0
imageurl = http://10.1.10.50/image.jpg
crosshairx = 0.5
crosshairy = 0.5
crosshaircolor = lime
crosshairthickness = 2
crosshairsize = 20
crosshairgap = 5
focusurl = http://10.1.10.50/control?p=focus
focusstep = 200
widgetwidth = 512
widgetheight = 288

[LS_PLC]
ip = 192.168.10.220
port = 2004

[LS_PLC_TARGETS]
%dw250 = Mold1
%dw256 = Mold2
%dw262 = Mold3
%dw288 = Mold4
%dw276 = Mold5
%dw282 = Mold6
%dw268 = Billet_Temp
%dw40 = At_Temp
%dw50 = At_Pre

[SETTINGS]
password = 1234
logpath = logs
snapshotpath = snapshots
autosave = True

[LOGGING]
rotationmode = BILLET
cycleidletime = 30
cyclethresholdpress = 20

[HEADERS]
csv = Date,Time,Temperature,메인압력,빌렛길이,콘테이너온도 앞쪽,콘테이너온도 뒷쪽,생산카운터,현재속도,압출종료 위치,Mold1,Mold2,Mold3,Mold4,Mold5,Mold6,Billet_Temp,At_Pre,At_Temp
console = | Temp  | 압력  | 빌렛L | 콘(앞)| 콘(뒤)| 카운트| 속도 | 종료 | Mold1 | Mold2 | Mold3 | Mold4 | Mold5 | Mold6 | BillT | AtPre | AtTmp

[THRESHOLDS_VALUE]
speed = 
press = 400.0
spot = 400.0
temp_f = 400.0
temp_b = 
billet = 
billet_temp = 
at_temp = 
at_pre = 
count = 
endpos = 
master_on = 

[THRESHOLDS_ENABLE]
speed = False
press = True
spot = True
temp_f = True
temp_b = False
billet = False
billet_temp = False
at_temp = False
at_pre = False
count = False
endpos = False
master_on = True
"""

def test_read():
    parser = configparser.ConfigParser()
    try:
        parser.read_string(config_content)
        print("Successfully read config string.")
        print("Sections:", parser.sections())
        if parser.has_section("LS_PLC_TARGETS"):
            print("LS_PLC_TARGETS keys:", parser.options("LS_PLC_TARGETS"))
            
        # Check SETTINGS
        print("Password:", parser.get("SETTINGS", "Password", fallback="MISSING"))
        
    except Exception as e:
        print(f"Error reading config: {e}")

if __name__ == "__main__":
    test_read()
