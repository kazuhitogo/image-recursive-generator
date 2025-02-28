import boto3
from botocore.config import Config
from tools import *
import tools
from time import sleep
import random
from logger import DualLogger
import argparse

logger = DualLogger("logs")


system_prompt = '''
あなたは几帳面かつ真面目で詳細の作り込みも厭わない完璧主義の画家 AI です。
ユーザーは画像のお題を与えます。お題の画像を svg 形式で作って svg2png tool を用いてください。
svg2png tool を使うと AI が作成した svg の画像を png 形式で AI に返します。
AI はユーザーから返された画像を再度チェックして修正した svg 形式で作って svg2png tool を使って・・・というのを繰り返し画像を作り込んでいってください。
ユーザーのお題を十分に満たしたと思ったら complete tool を使って完了したことを教えて下さい。
ただし、 AI は画像を作成したり修正する前に AI の思考を都度 write ツールを追記モードで必ず 英語で./work/thinking_en.txt に記録し、日本語で./work/thinking_jp.txtに記録してください。
AI はユーザーとの会話は不要なので、与えたツールだけを使って粛々と作業してください。'''


def initialize_bedrock_client():
    return boto3.client(
        'bedrock-runtime',
        region_name='us-west-2',
        config=Config(
            connect_timeout=300,
            read_timeout=300,
            retries={
                "mode": "standard",
                "total_max_attempts": 5,
            },
        ),
    )


def create_initial_message(title):
    return [{"role": "user", "content": [{"text": title}]}]


def converse_with_model(brt, messages):
    return brt.converse(
        system=[{'text': system_prompt}],
        modelId='us.anthropic.claude-3-7-sonnet-20250219-v1:0',
        messages=messages,
        toolConfig={"tools": get_tools()},
        inferenceConfig={"maxTokens": 8192, 'temperature': 1},
    )


def retry_converse_with_model(brt, messages, max_retries=10):
    initial_delay = 1  # Start with 1 second delay
    max_delay = 120  # Cap maximum delay at 120 seconds

    for attempt in range(max_retries):
        try:
            response = converse_with_model(brt, messages)
            return response
        except Exception as e:
            if attempt < max_retries - 1:
                # Calculate delay with exponential backoff: 2^attempt seconds
                delay = min(initial_delay * (2**attempt), max_delay)

                # Add random jitter between 0 and 1 second
                jitter = random.uniform(0, 1)
                total_delay = delay + jitter

                print(
                    f"エラーが発生しました: {e}. {total_delay:.1f}秒後にリトライします。(試行 {attempt + 1}/{max_retries})"
                )
                sleep(total_delay)
            else:
                print(f"最大リトライ回数に達しました。エラー: {e}")
                raise


def list_tools():
    module_attributes = set(dir(tools))
    imported_functions = [
        attr for attr in module_attributes if callable(getattr(tools, attr))
    ]
    return imported_functions


def process_tool_use(assistant_content, tools: list):
    tool_name = assistant_content['toolUse']['name']
    args = assistant_content['toolUse']['input']
    if tool_name not in tools:
        raise ValueError(f"Unknown tool: {tool_name}")
    tool_function = globals()[tool_name]

    if tool_name != 'complete':
        tool_result = tool_function(**args)
        print(tool_result)
        if tool_name == 'svg2png':
            return {
                "toolResult": {
                    "toolUseId": assistant_content['toolUse']['toolUseId'],
                    "content": [
                        {"text": 'あなたが作った画像です'},
                        {"image": {'format': 'png', 'source': {'bytes': tool_result}}},
                    ],
                }
            }, True
        else:
            return {
                "toolResult": {
                    "toolUseId": assistant_content['toolUse']['toolUseId'],
                    "content": [{"text": tool_result}],
                }
            }, True
    else:
        return None, tool_function(**args)


def main():
    # コマンドライン引数を設定
    parser = argparse.ArgumentParser(description='AIによる画像生成')
    parser.add_argument(
        '--title',
        type=str,
        default='ドラえもん',
        help='生成する画像のお題 (デフォルト: ドラえもん)',
    )
    args = parser.parse_args()

    print('work directory の初期化')
    print(rm_recursive('./work'))
    print(mkdir_p('./work'))
    print('work directory の初期化完了')

    print('image directory の初期化')
    print(rm_recursive('./image'))
    print(mkdir_p('./image'))
    print('image directory の初期化完了')

    brt = initialize_bedrock_client()
    messages = create_initial_message(args.title)  # コマンドライン引数を使用
    tools = list_tools()
    is_loop = True

    while is_loop:
        try:
            response = retry_converse_with_model(brt, messages)
        except Exception as e:
            print(f"会話に失敗しました: {e}")
            break

        output = response["output"]
        logger.log(f"message: {output['message']}")

        messages.append(output['message'])

        user_content = []
        for assistant_content in output['message']['content']:
            logger.log(f"Persed contents: {assistant_content}")
            if 'toolUse' in assistant_content:
                tool_result, is_loop = process_tool_use(assistant_content, tools)
                if tool_result:
                    user_content.append(tool_result)
            else:
                print('loop done')
                is_loop = False
                print(messages[-1])

        if user_content:
            messages.append(
                {
                    'role': 'user',
                    "content": user_content,
                }
            )
            print(messages[-1])

        print(f"Is loop continuing: {is_loop}")


if __name__ == "__main__":
    main()
