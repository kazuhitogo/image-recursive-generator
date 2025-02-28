import os
import base64
import cairosvg
import re
import shutil

tools = []

tools.append(
    {
        'toolSpec': {
            'name': 'write',
            # ファイルにテキストを書き込むツール。
            # 返り値は"File written successfully."
            # エラーが発生した場合は Error: という文言から始まる言葉が返る。
            'description': '''A tool to write text to a file.
The return value is "File written successfully".
If an error occurs, the output will start with "Error:"''',
            'inputSchema': {
                'json': {
                    'type': 'object',
                    'properties': {
                        'content': {
                            'type': 'string',
                            # ファイルに書き込みたい内容
                            'description': 'Content to be written to the file',
                        },
                        'write_file_path': {
                            'type': 'string',
                            # テキストを書き込むファイルパス
                            'description': 'File path to write text',
                        },
                        'mode': {
                            'type': 'string',
                            'enum': ['wt', 'at'],
                            # 上書きならば wt, 追記なら at を格納
                            'description': 'If overwriting, store as "wt", if appending, store as "at".',
                        },
                    },
                    'required': ['content', 'write_file_path', 'mode'],
                }
            },
        }
    }
)

tools.append(
    {
        'toolSpec': {
            'name': 'svg2png',
            'description': '''svg の文字列を渡すと、png 形式のバイナリ文字列を返すツール。
ただし、裏側で cairosvg を使っていることに注意。例えば width や height の値が必須です。''',
            'inputSchema': {
                'json': {
                    'type': 'object',
                    'properties': {
                        'content': {
                            'type': 'string',
                            'description': 'svgの文字列',
                        },
                    },
                    'required': ['content'],
                }
            },
        }
    }
)

tools.append(
    {
        'toolSpec': {
            'name': 'complete',
            # 全ての処理が完了したことを知らせるツール
            'description': 'A tool to notify when all processing is complete',
            'inputSchema': {
                'json': {
                    'type': 'object',
                    'properties': {
                        'content': {
                            'type': 'string',
                            # 処理完了のメッセージ
                            'description': 'A message for processing complete',
                        },
                    },
                    'required': ['content'],
                }
            },
        },
    }
)


def get_tools():
    return tools


def svg2png(content):
    """
    SVG文字列を受け取り、SVGファイルとPNGファイルを保存し、
    PNGファイルをbase64エンコードして返す関数

    Args:
        content (str): SVG形式の文字列

    Returns:
        str: PNGファイルのbase64エンコード文字列
    """
    # ディレクトリが存在しない場合は作成
    os.makedirs('image', exist_ok=True)

    # ファイル名の基本部分
    base_svg_path = 'image/image.svg'
    base_png_path = 'image/image.png'

    # 既存のファイルが存在する場合、それらをリネームする
    if os.path.exists(base_svg_path) or os.path.exists(base_png_path):
        # 既存の連番ファイルを探して最大の連番を見つける
        max_seq = 0
        pattern = re.compile(r'image/image-(\d+)\.(?:svg|png)')

        for filename in os.listdir('image'):
            match = re.match(r'image-(\d+)\.(svg|png)', filename)
            if match:
                seq_num = int(match.group(1))
                max_seq = max(max_seq, seq_num)

        # 新しい連番を使用（5桁のゼロ埋め）
        new_seq = max_seq + 1
        new_seq_str = f"{new_seq:05d}"

        # 既存のファイルをリネーム
        if os.path.exists(base_svg_path):
            os.rename(base_svg_path, f'image/image-{new_seq_str}.svg')
        if os.path.exists(base_png_path):
            os.rename(base_png_path, f'image/image-{new_seq_str}.png')

    # SVGファイルを保存
    with open(base_svg_path, 'w', encoding='utf-8') as f:
        f.write(content)

    # SVGをPNGに変換
    cairosvg.svg2png(url=base_svg_path, write_to=base_png_path)

    # PNGファイルをbase64エンコード
    with open(base_png_path, 'rb') as f:
        png_data = f.read()

    return png_data


def complete(content: str) -> bool:
    print(content)
    return False


def rm_recursive(remove_dir_path: str) -> str:
    try:
        normalized_path = os.path.abspath(os.path.normpath(remove_dir_path))
        if not os.path.exists(normalized_path):
            return f'Error: Directory does not exist {normalized_path}'
        if not os.path.isdir(normalized_path):
            return f'Error: Not a directory {normalized_path}'
        important_dirs = ['/', '/etc', '/bin', '/sbin', '/var', '/usr', '/home']
        if normalized_path in important_dirs:
            return f'Error: Cannot remove important system directory {normalized_path}'
        shutil.rmtree(normalized_path)
        return f'Successfully removed directory and its contents {normalized_path}'
    except Exception as e:
        return f'Error: {str(e)}'


def mkdir_p(directory_name):
    try:
        if os.path.exists(directory_name):
            return 'Already exists a directory.'
        os.makedirs(directory_name, exist_ok=True)
        return 'Directory created successfully'
    except Exception as e:
        # エラーが発生した場合
        return f'Error: {str(e)}'


def write(content='', write_file_path='', mode='') -> str:
    # パラメータのチェック
    error_messages = []
    if content == '':
        error_messages.append('content is empty')
    if write_file_path == '':
        error_messages.append('write_file_path is empty')
    if mode == '':
        error_messages.append('mode is empty')

    # エラーメッセージがある場合は、それらを返す
    if error_messages:
        return 'Error: ' + ', '.join(error_messages)

    # すべてのパラメータが正しい場合、ファイル書き込みを実行
    try:
        with open(write_file_path, mode) as f:
            f.write(content + '\n')
        return 'File written successfully.'
    except Exception as e:
        return f'Error: An unexpected error occurred: {str(e)}'


# debug 用
if __name__ == '__main__':
    svg2png(
        '''<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="60">
  <rect x="0" y="0" width="100" height="60" fill="#ddd" />
  <polygon points="50 10, 70 30, 50 50, 30 30" fill="#99f" />
</svg>'''
    )
    exit()
