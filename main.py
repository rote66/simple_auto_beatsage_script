import argparse
import json
import os
import sys
import time

import requests
from tinytag import TinyTag

base_url = 'https://beatsage.com'
create_url = base_url + "/beatsaber_custom_level_create"

headers_beatsage = {
    'authority': 'beatsage.com',
    'method': 'POST',
    'path': '/beatsaber_custom_level_create',
    'scheme': 'https',
    'accept': '*/*',
    'accept-encoding': 'gzip, deflate, br',
    'accept-language': 'zh-CN,zh;q=0.9',
    'origin': base_url,
    'pragma': 'no-cache',
    'referer': base_url,
    'sec-ch-ua': '"Not?A_Brand";v="8", "Chromium";v="108", "Google Chrome";v="108"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
    'x-kl-ajax-request': 'Ajax_Request'
}


def get_mp3_tag(file):
    tag = TinyTag.get(file, image=True)
    title = tag.title
    artist = tag.artist
    cover = tag.get_image()
    if not cover:
        cover = ''
    return title, artist, cover


def get_map(file, outputdir, diff, modes, events, env, tag):
    audio_title, audio_artist, cover_art = get_mp3_tag(file)
    filename = os.path.splitext(os.path.basename(file))[0]
    if str(audio_title) == '':
        audio_title = filename
    print('Current Processing file: "' + filename + '"')
    payload = {
        'audio_metadata_title': audio_title,
        'audio_metadata_artist': audio_artist,
        'difficulties': diff,
        'modes': modes,
        'events': events,
        'environment': env,
        'system_tag': tag
    }
    if cover_art == '':
        files = {
            "audio_file": open(file, "rb").read()
        }
    else:
        files = {
            "audio_file": ("audio_file", open(file, "rb").read(), "audio/mpeg"),
            "cover_art": ("cover_art", cover_art, "image/jpeg")
        }
    response = requests.request("POST", create_url, headers=headers_beatsage, data=payload, files=files)
    if response.status_code == 413:
        print("Error:File Limits 32MB or 10min")
        return
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        print(err)
        return
    map_id = json.loads(response.text)['id']
    heart_url = base_url + "/beatsaber_custom_level_heartbeat/" + map_id
    download_url = base_url + "/beatsaber_custom_level_download/" + map_id
    sys.stdout.write("Processing")
    while json.loads(requests.request("GET", heart_url, headers=headers_beatsage).text)['status'] != "DONE":
        time.sleep(3)
        sys.stdout.write('.')
        sys.stdout.flush()
    print('')
    print('File: "' + filename + '" process done\n---------------------------\n ')
    response = requests.request("GET", download_url, headers=headers_beatsage)
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        print(err)
        return
    with open(outputdir + '/' + filename + '.zip', 'wb') as f:
        for chunk in response.iter_content(chunk_size=128):
            f.write(chunk)


def get_args():
    parser = argparse.ArgumentParser(description='Simple auto beatsage from local files by rote66')
    parser.add_argument('--input', '-i', type=str, default='/', help='Input folder', required=True)
    parser.add_argument('--output', '-o', type=str, default='/', help='Output folder')
    parser.add_argument('--difficulties', '-d', type=str, default='Hard,Expert,ExpertPlus,Normal',
                        help='difficulties : Hard,Expert,ExpertPlus,Normal')
    parser.add_argument('--modes', '-m', type=str, default='Standard,90Degree,NoArrows,OneSaber',
                        help='modes : Standard,90Degree,NoArrows,OneSaber')
    parser.add_argument('--events', '-e', type=str, default='DotBlocks,Obstacles,Bombs',
                        help='events : DotBlocks,Obstacles,Bombs')
    parser.add_argument('--environment', '-env', type=str, default='DefaultEnvironment',
                        help='environment : Default : DefaultEnvironment, Origins : Origins, Triangle : '
                             'TriangleEnvironment, Nice : NiceEnvironment Big Mirror : BigMirrorEnvironment, '
                             '\nImagine Dragons : DragonsEnvironment, K/DA : KDAEnvironment Monstercat : '
                             'MonstercatEnvironment, Crab Rave : CrabRaveEnvironment, Panic at the Disco! : '
                             'PanicEnvironment \nRocket League : RocketEnvironment,Green Day : GreenDayEnvironment, '
                             'Green Day Grenade : GreenDayGrenadeEnvironment \nTimbaland : TimbalandEnvironment, '
                             'FitBeat : FitBeatEnvironment, Linkin Park : LinkinParkEnvironment')
    parser.add_argument('--model_tag', '-t', type=str, default='v2', help='model : v1,v2,v2-flow')
    if 1 < len(sys.argv) < 3 and os.path.exists(sys.argv[1]):
        return parser.parse_args(['-i', sys.argv[1]])
    else:
        return parser.parse_args()


if __name__ == '__main__':
    try:
        args = get_args()
        file_dict = {}
        if args.output == '/':
            args.output = args.input
        for filename in os.listdir(args.input + '/'):
            if filename.lower().endswith((
                    '.opus', '.flac', '.webm', '.weba', '.wav', '.ogg', '.m4a', '.mp3', '.oga', '.mid', '.amr',
                    '.aac', '.wma')):
                file_dict[filename] = ''
        current_count = 0
        for key in file_dict:
            current_count += 1
            print(f"\rCurrent Process {current_count}/{len(file_dict)}")
            if os.path.exists(args.output + '/' + os.path.splitext(os.path.basename(key))[0] + '.zip'):
                print("Detect zip exist , Skip " + '"' + os.path.basename(key) + '"' + " File")
                continue
            get_map(os.path.join(args.input + '/', key), args.output, args.difficulties, args.modes,
                    args.events, args.environment, args.model_tag)
        print('All Done!')
    except Exception as e:
        print(e)
    finally:
        os.system('pause')
        sys.exit()
