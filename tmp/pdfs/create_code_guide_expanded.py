# 既存の解説PDFを、改修・新規作成・技術選定理由が追える構成に更新するスクリプトです。
from pathlib import Path
import ast
import re
import textwrap
import subprocess
import hashlib

ROOT = Path(__file__).resolve().parents[2]
# 前版と同じフォント・表・コード枠を使い、見た目を統一する。
previous = (ROOT / 'tmp/pdfs/create_code_guide.py').read_text(encoding='utf-8-sig')
helpers = previous[:previous.index("page('Giftia 今回の編集内容とコード解説'")]
exec(helpers, globals())
OUT = ROOT / 'output/pdf/Giftia_今回の編集内容とコード解説_初学者向け.pdf'
parts=[]
source_checks=[]

def begin(title,lead,part):
    page(title,lead)
    parts.append(part)

def find_chunk(rel,start,end=None,strip_comments=True):
    lines=(ROOT/rel).read_text(encoding='utf-8-sig').splitlines()
    a=next(i for i,line in enumerate(lines) if start in line)
    b=len(lines)
    if end is not None:
        b=next(i for i in range(a+1,len(lines)) if end in lines[i])
    selected=lines[a:b]
    if strip_comments:
        selected=[line for line in selected if line.strip() and not line.lstrip().startswith(('#','//'))]
    source_checks.append({'file':rel,'first_line':a+1,'last_line':b})
    story.append(P('参照：'+(ROOT/rel).as_posix()+f'（{a+1}〜{b}行）','small'))
    return textwrap.dedent('\n'.join(selected)).rstrip()

def function_code(rel,name):
    text=(ROOT/rel).read_text(encoding='utf-8-sig')
    lines=text.splitlines()
    node=next(n for n in ast.parse(text).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name)
    a=min([node.lineno]+[d.lineno for d in node.decorator_list])-1
    b=node.end_lineno
    omit=set()
    if node.body and isinstance(node.body[0],ast.Expr) and isinstance(node.body[0].value,ast.Constant) and isinstance(node.body[0].value.value,str):
        omit.update(range(node.body[0].lineno-1,node.body[0].end_lineno))
    selected=[line for i,line in enumerate(lines[a:b],a) if i not in omit and line.strip() and not line.lstrip().startswith('#')]
    source_checks.append({'file':rel,'first_line':a+1,'last_line':b})
    story.append(P('参照：'+(ROOT/rel).as_posix()+f'（{a+1}〜{b}行）','small'))
    return '\n'.join(selected)

def compact_code(text):
    block=Code(text)
    block.leading=11
    block.height=len(block.lines)*block.leading+24
    story.append(block)

def why(text):
    h('なぜ、この作り方・順序にしたのか')
    body(text)

begin('Giftia コード解説・追記版','初学者向け｜改修したコードと、新しく作ったファイルを分けて学ぶ\n2026-11-17の読みやすく整理したコードに対応。','はじめに')
body('この資料では、ルーム機能を作るために「以前からあるプログラムのどこへ、何を足したか」と「新しいファイルをなぜ分けて作ったか」を整理します。追加したコードの意味だけでなく、ライブラリを使った理由と、処理をこの順番にした理由も説明します。')
story.append(Architecture())
story.append(table([
['区分','何を説明するか'],
['A　既存プログラムの改修','main.py、database.py、検索画面、Next.js設定。追加・変更したコードを機能ごとに示す。'],
['B　新規ファイルの作成','ルーム用API、通信、画面、カレンダー、共通部品、SQL、祝日データ、テスト。目的・処理・必要性を説明する。'],
['既存資産の取り込み','ローカルで不足していた起動構成などは、既存のorigin/mainから取り込んだ。自分たちが一から作った新機能とは区別する。'],
],[W*.32,W*.68]))
h('最初に押さえること')
body('画面とAPIは手元のPC、保存先は班のAzure MySQLです。画面からDBへ直接接続せず、APIが入力を確認してから読み書きします。画面が覚える状態と、DBへ確定して保存したデータは別です。')
story.append(note('今回の実装範囲：ルーム作成・幹事同時登録・保存・取得・負担額表示・受け取り期限の入力チェック。参加操作、プロフィール、推薦、投票、営業日の逆算は後続の範囲です。'))
h('資料の使い方')
body('まず2ページの分類、3〜4ページの選定理由と全体の流れを読みます。次にAで既存への追加箇所、Bで新規ファイルを確認してください。コードは現行ファイルから抜粋し、コメント・空行や長い部分を必要に応じて省略・整形しています。')
body('参照フォルダー：'+ROOT.as_posix()+'\nコード枠は説明用の抜粋です。ファイル全体を置き換えるためのコードではありません。')

begin('変更したファイルの分類','「新機能のための新規作成」と「既存構成の復元」を混同しないようにします。','はじめに')
story.append(table([
['A　既存へ追加・変更したもの','今回の変更点'],
['backend/main.py','ルームAPIの登録と、CORSでPOSTを許可。検索APIは継続。'],
['backend/database.py','添付の書き込み関数を取り込み。insert、execute、transactionを追加。既存の接続・取得を再利用。'],
['frontend/app/page.tsx','既存検索画面にルーム作成へのリンクを追加。旧frontend/page.tsxからapp配下へ配置を合わせた。'],
['frontend/next.config.ts','既存設定を取り込み、画面外のsharedフォルダーを参照する設定を追加。'],
],[W*.43,W*.57]))
story.append(Spacer(1,12))
story.append(table([
['B　新規に作ったもの','作成目的'],
['backend/rooms.py','ルームに関する入力確認・保存・取得をまとめる。'],
['frontend/lib/rooms.ts','画面から呼ぶ通信・日付確認をまとめる。'],
['frontend/app/rooms/new/page.tsx','ルーム作成フォームを表示する。'],
['frontend/app/rooms/[roomId]/page.tsx','保存済みのルームを番号で取得して表示する。'],
['frontend/app/rooms/DateCalendar.tsx','選べない日を除いたカレンダーを表示する。'],
['frontend/app/rooms/RoomShell.tsx・rooms.css','共通の枠と見た目を定義する。'],
['db/schema.sql・shared/japan-holidays.json','保存先の表と、共通の祝日データを用意する。'],
['backend/test_rooms.py','壊していないかを、班のDBを使わず確認する。'],
],[W*.53,W*.47]))
h('origin/mainから取り込んだ既存資産')
body('package.json、package-lock.json、tsconfig.json、eslint.config.mjs、app/layout.tsx、app/globals.css、app/ResultCard.tsx、lib/api.tsなど。ローカルでは新しいファイルに見えても、既存の起動・検索構成を復元したものです。業務機能を一から追加したものとしては数えません。')
body('その後の読みやすくする整理では、長い式を変数に分け、処理順の日本語コメントを追加しました。これ自体は機能追加ではありません。')

begin('ライブラリ・技術の選定理由','既存の採用技術を継続した理由と、今回新しく依存を増やさなかった理由です。','設計の理由')
body('基本方針は、講義・配布コードのNext.js → FastAPI → MySQLを維持することです。以下は、今回のために全技術を新規比較した結果ではなく、既存構成を生かすための判断です。')
story.append(table([
['技術・ライブラリ','役割','今回これを使う理由'],
['Next.js / React','画面、URLごとのページ、状態管理','既存検索画面を再利用できる。/rooms/newと/rooms/[roomId]を分け、入力・読み込み中の表示を扱える。[1]'],
['FastAPI','APIの受付・JSON応答','既存検索APIにルーム処理を足せる。入力検証とSwaggerによる動作確認を利用できる。[2]'],
['Pydantic','入力・出力の形を定義','FastAPIで使う入力モデルを利用し、整数・必須・文字数・日付をAPI側で確認する。[2]'],
['PyMySQL','PythonからMySQLを操作','既存の接続関数とSQLを継続できる。値の分離とcommit・rollbackを明示できる。[3]'],
['Uvicorn','FastAPIを起動するサーバー','配布コードの起動方法を継続。新しいサーバー構成を増やさない。'],
['python-dotenv','既存の接続設定を読み込む','接続情報をコードに直書きせず、API側で使う既存構成を維持。設定内容の公開はしない。'],
['TypeScript / ESLint','型の確認・静的チェック','既存の開発構成を利用し、書き間違いや問題を実行前にも見つける。'],
],[W*.24,W*.24,W*.52]))
h('追加インストールをせずに使った仕組み')
body('Python標準のmath.ceilで負担額を切り上げ、datetimeで日付、jsonで祝日一覧、contextlib.contextmanagerで保存の確定・取り消しをまとめています。画面側のfetch、Intl、Date、AbortControllerはブラウザーの標準機能です。')
body('カレンダーは「月表示・日付選択・休日の無効化」に絞り、ReactとDateで作りました。外部カレンダー、状態管理、ORMの追加は今回は行わず、既存の書き方を学びやすくしています。FastAPI等はフレームワーク、MySQLはDB、mathは標準モジュールであり、すべてが同じ種類のライブラリではありません。')
story.append(P('補足：react-domは画面描画の既存依存です。cryptographyも既存のrequirements.txtにありますが、今回のルーム処理では直接呼び出していません。今回新たに選定・追加したものではありません。','small'))
story.append(P('公式情報：[1] Next.js公式（Server and Client Components）、[2] FastAPI公式（Features）、[3] PyMySQL公式（Examples）。URLは巻末。選定理由は今回の構成に基づく判断。','small'))

begin('なぜ、この処理の順番にしたか','ボタンを押してから、保存した情報が表示されるまでの流れです。','設計の理由')
story.append(Architecture())
story.append(table([
['順番','何をするか','この順番にする理由'],
['1　画面で確認','必須・日付などを確認する。','入力ミスにすぐ気付けるようにし、不要な通信を減らす。'],
['2　POSTで依頼','入力をJSONにしてAPIへ送る。','画面にDB接続情報やSQL処理を持たせない。'],
['3　APIで再確認','モデルと専用関数で入力を検証。','画面を通さない直接送信にも同じルールを適用する。'],
['4　ルームを登録','ルームを追加し、idを取得。','メンバーを所属させる先の番号が先に必要。'],
['5　幹事を登録・関連付け','幹事メンバーを追加し、ルームに幹事idを記録。','作成時に発行される番号を使って結び付けるため。'],
['6　まとめて確定','成功時commit、失敗時rollback。','ルームだけ残るなど、途中までの保存を防ぐ。'],
['7　結果を返して移動','保存が成功してからルーム画面へ移る。','保存前に成功画面を表示しないようにする。'],
['8　GETで再取得・表示','URLの番号で取得し、setRoomで表示に反映。','作成直後も再訪時も、同じ保存済み情報の取得方法を使える。'],
],[W*.22,W*.35,W*.43]))
why('画面の状態だけなら再読み込みで失われます。一方、入力途中のたびにDBへ書く必要はありません。入力中はuseState、作成を依頼したときはPOST、保存済み情報を読むときはGET、と役割を分けています。')
story.append(note('トランザクションはルームと幹事の登録全体で1回。1つずつ別々に確定すると、途中の失敗で片方だけ残るため、今回はtransactionを選んでいます。'))

begin('A-1｜main.pyに追加したコード','既存のAPIの入口へ、ルームAPIをつなぎました。','A｜既存プログラムの改修')
source('backend/main.py')
h('追加①　ルームAPIを読み込む')
code('from rooms import router as rooms_router')
body('rooms.pyのrouterを、rooms_routerという名前で読み込みます。routerは、ルーム用のURLと関数をまとめたものです。読み込むだけではAPIの入口につながらないので、次に登録します。')
h('追加②　FastAPIへ登録する')
code('app.include_router(rooms_router)')
body('これにより、rooms.pyのPOST /api/roomsとGET /api/rooms/{room_id}を受け付けられるようになります。既存の/api/searchはそのまま残します。')
h('変更③　CORSでPOSTも許可する')
code('''app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)''')
story.append(table([
['以前','変更後の意味'],
['allow_methods=["GET"]','取得だけでなく、ルーム作成のPOSTも許可する。'],
['allow_headers=["*"]','JSON送信に使うContent-Typeを明示する。'],
['allow_origins=origins','許可する画面のURLだけを使う方針は維持する。'],
],[W*.43,W*.57]))
why('検索とルームでFastAPIアプリを別々に増やすより、既存の入口へ登録する方が起動方法をそろえられます。処理本体はrooms.pyへ分け、main.pyは入口の設定を担当します。CORSの制限を適用するのはブラウザーで、許可情報を返すのはAPIです。')

begin('A-2｜database.pyに書き込み関数を追加','既存には接続と取得がありました。添付の書き込み処理を取り込み、共通関数として使えるようにしました。','A｜既存プログラムの改修')
h('追加①　insert：1件の登録を確定し、番号を返す')
code(function_code('backend/database.py','insert'))
body('cur.executeで登録し、lastrowidで新しい行の番号を受け取ります。commitで確定し、失敗ならrollbackして、raiseで失敗を呼び出し元へ伝えます。finallyでは必ず接続を閉じます。')
h('追加②　execute：更新・削除の結果を返す')
code(function_code('backend/database.py','execute'))
body('登録idの代わりに、影響した行数changed_rowsを返します。0は、対象がない場合だけでなく値が変わらない場合もあります。これら2関数は追加済みですが、ルームと幹事の同時保存には、次ページのtransactionを使います。')

begin('A-3｜database.pyにtransactionを追加','複数の登録を、全部成功か全部取り消しかにまとめるための関数です。','A｜既存プログラムの改修')
code(function_code('backend/database.py','transaction'))
story.append(table([
['コード','追加した役割'],
['@contextmanager','この関数をwith transaction()として使えるようにする。'],
['conn = get_connection()','複数のSQLで共通して使う接続を作る。'],
['yield cur','一時的に呼び出し元へ戻り、withの中のSQLを実行する。'],
['conn.commit()','withの中がすべて成功したら、保存をまとめて確定する。'],
['rollback() / raise','失敗したら取り消し、失敗したことを呼び出し元へ伝える。'],
['finally / close()','成功・失敗にかかわらず、接続を閉じる。'],
],[W*.40,W*.60]))
why('今回の作成には「ルーム追加 → 幹事追加 → ルームに幹事idを記録」の3処理があります。別々にcommitするinsert・executeを並べると途中まで残るため、同じ接続でまとめます。既存のget_connectionとfetch_allは再利用しています。')
h('既存の取得処理は、名前を付けて読みやすくした')
code('''rows = cur.fetchall()
return rows''')
body('これはreturn cur.fetchall()を2行に分けた整理です。新しい取得機能を足したわけではありません。')

begin('A-4｜既存画面と設定へ追加したコード','ルームへ入る入口を増やし、既存の起動・検索構成を生かしました。','A｜既存プログラムの改修')
source('frontend/app/page.tsx')
h('追加①　検索画面から作成画面へのリンク')
code('''import Link from "next/link";

<Link href="/rooms/new">
  みんなで贈るルームを作る →
</Link>''')
body('既存の商品検索画面に移動用リンクを足しました。クリックすると、新しく作った/rooms/newを開きます。ルームの作成処理やDB保存を、このリンク自体が行うわけではありません。')
source('frontend/next.config.ts')
h('追加②　共通祝日データを参照する設定')
code('''import path from "node:path";

const nextConfig: NextConfig = {
  turbopack: { root: path.resolve(__dirname, "..") },
};''')
body('frontendの外にあるshared/japan-holidays.jsonを参照するため、解決対象のルートをリポジトリ側へ広げています。新しい外部ライブラリではなく、Node.js標準のpathを使っています。')
why('画面とAPIで祝日データを別々に持つと、更新漏れで判定がずれるおそれがあります。1つのJSONを共有できるよう、既存設定に必要な部分を追加しました。')
h('新規作成と区別した既存資産の取り込み')
body('検索画面・ResultCardはapp配下に配置を合わせました。package.json、型設定、共通layout、基本CSS、検索用lib/api.tsなどはorigin/mainの整備済み構成を取り込みました。今回それぞれに新しい業務機能を作り込んだ、という意味ではありません。プログラム先頭の役割コメントも追加しました。')

begin('B-1｜rooms.py：ルーム用APIを作る理由','新規ファイル｜入力のルール、作成、取得、返却を「ルーム」という単位でまとめます。','B｜新規ファイルの作成')
source('backend/rooms.py')
why('検索の関数があるmain.pyへすべて追記すると、設定・検索・ルームの処理が混ざります。APIRouterでルーム用のURLをまとめ、main.pyから登録する構成にしました。')
code('router = APIRouter(prefix="/api/rooms", tags=["相談ルーム"])')
body('prefixは共通のURLの先頭です。@router.post("")なら/api/rooms、@router.get("/{room_id}")なら/api/rooms/1などになります。tagsはSwaggerで分類するための名前です。')
h('入力モデル：保存する前にルールを確認する')
code(find_chunk('backend/rooms.py','class RoomCreate(BaseModel):','    @field_validator'))
body('RoomCreateは受け取る形です。Fieldで文字数や整数の範囲を決めます。str_strip_whitespaceは前後の空白を除き、extra="forbid"は定義のない項目を拒否します。')
story.append(table([
['項目','確認する内容'],['title / nickname','必須の文字列。最大100文字／30文字。'],['budget_total / member_count','1以上の整数。MySQLのINTに収まる値。'],['deliver_by','正しい日付形式、今日以降、土日祝日以外。'],['Room','画面へ返す項目を決める出力モデル。'],
],[W*.42,W*.58]))
body('PydanticはFastAPIの入力検証を使うために利用しています。画面の入力制限をすり抜けた直接送信にも、同じルールを適用できます。')

begin('B-2｜rooms.py：作成処理を順に読む','新規ファイルの中身｜ルームと幹事を登録し、関連付けてから結果を返します。','B｜新規ファイルの作成')
source('backend/rooms.py')
code('''@router.post("", response_model=Room, status_code=201)
def create_room(body: RoomCreate):
    try:
        with transaction() as cur:
            cur.execute(
                "INSERT INTO consultations "
                "(title, budget_total, member_count, deliver_by) "
                "VALUES (%s, %s, %s, %s)",
                (body.title, body.budget_total, body.member_count, body.deliver_by),
            )
            room_id = cur.lastrowid
            cur.execute(
                "INSERT INTO consultation_members "
                "(consultation_id, nickname) VALUES (%s, %s)",
                (room_id, body.nickname),
            )
            organizer_id = cur.lastrowid
            cur.execute(
                "UPDATE consultations SET organizer_id = %s WHERE id = %s",
                (organizer_id, room_id),
            )
    except (pymysql.MySQLError, EnvironmentError):
        raise storage_unavailable() from None''')
story.append(table([
['コードのまとまり','目的'],['RoomCreate → create_room','入力チェックが通った情報で保存を始める。'],['最初のINSERT / lastrowid','ルームを追加し、所属先に使う番号を得る。'],['2つ目のINSERT / lastrowid','幹事メンバーを追加し、その番号を得る。'],['UPDATE','ルームに幹事の番号を記録する。'],['transaction / except','まとめて確定。失敗時は取り消し、画面へ503を返す。'],
],[W*.43,W*.57]))
body('保存が成功した後はsaved_roomに保存内容をまとめ、to_roomで表示用に整えます。201は作成成功を表します。SQLの値は%sと別引数で渡し、入力をSQLの命令に直接つなげません。')

begin('B-3｜rooms.py：取得と返却の処理','新規ファイルの中身｜URLの番号で保存済み情報を探し、負担額を加えて返します。','B｜新規ファイルの作成')
source('backend/rooms.py')
code('''rows = fetch_all(
    """SELECT c.id AS room_id, c.title, c.budget_total,
              c.member_count, c.deliver_by,
              m.nickname AS organizer_nickname
       FROM consultations c
       JOIN consultation_members m
         ON m.id = c.organizer_id AND m.consultation_id = c.id
       WHERE c.id = %s""",
    (room_id,),
)''')
body('SELECTは取得、JOINはルームと幹事の表を結び付ける処理、WHEREは対象を番号で絞る処理です。(room_id,)は、要素が1つのタプルです。取得結果が0件なら404、接続などの失敗は503を返します。')
h('返す項目は一つずつ明記する')
code(function_code('backend/rooms.py','to_room'))
why('返却形を作成時と取得時でそろえると、画面が同じ形の情報を扱えます。負担額はmath.ceilで円単位に切り上げ、計算内容を読んで分かるようにしました。例：ダミー予算4,501円÷3人なら1,501円です。')
body('rowは項目名と値の組である辞書です。room_pathには/rooms/1のような表示先を入れます。これはファイルの保存先ではなく、画面のURLです。')

begin('B-4｜lib/rooms.ts：通信を分ける理由','新規ファイル｜画面から呼ぶ「作成」と「取得」の窓口です。','B｜新規ファイルの作成')
source('frontend/lib/rooms.ts')
why('各画面にfetchやエラー処理を重複させるより、通信先・JSON化・返却形を1か所へまとめる方が、接続先やエラーの扱いを直しやすくなります。画面は入力・表示を担当します。')
code('''const url = `${API}/api/rooms`;
const requestBody = JSON.stringify(input);
const response = await fetch(url, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: requestBody,
});
const roomData = await responseRoom(response);
return roomData;''')
story.append(table([
['まとまり','目的'],['RoomInput / Room','送る情報と返る情報を、それぞれTypeScriptの型にする。'],['JSON.stringify(input)','入力オブジェクトを、送信用のJSON文字列にする。'],['await fetch','APIのレスポンスが利用可能になるまで待つ。'],['await responseRoom','成功・失敗を確認し、本文をJSONとして読み取る。'],
],[W*.36,W*.64]))
h('取得ではGETを使う')
code('''const roomId = encodeURIComponent(id);
const url = `${API}/api/rooms/${roomId}`;
const response = await fetch(url, {
  cache: "no-store",
  signal: signal,
});
const roomData = await responseRoom(response);
return roomData;''')
body('getRoomは保存済み情報を読む処理です。encodeURIComponentは値をURLへ安全に組み込みます。signalは不要な通信を中止するために渡します。TypeScriptの型だけでは外部入力の実行時検証はできないため、API側の確認も残しています。')

begin('B-5｜lib/rooms.ts：日付と失敗の扱い','新規ファイルの中身｜選べない理由を返す関数と、通信結果を読み取る関数です。','B｜新規ファイルの作成')
source('frontend/lib/rooms.ts')
h('unavailableDate：順に確認し、理由を返す')
code('''const year = date.getUTCFullYear();
if (!supportedYears.includes(year)) {
  return "祝日データのある2026年・2027年から選んでください";
}
if (day < today) {
  return "今日以降を選んでください";
}
const holidayName = holidays[day];
if (holidayName) {
  return holidayName;
}
const weekday = date.getUTCDay();
if (weekday === 0 || weekday === 6) {
  return "土日には設定できません";
}
return null;''')
body('この前に、YYYY-MM-DD形式か、2月30日のような存在しない日でないかも確認しています。問題があれば理由の文字列、なければnullを返します。JavaScriptの曜日は日曜0・土曜6です。')
h('responseRoom：通信の成功と本文を確認する')
code('''if (response.ok) {
  const roomData: Room = await response.json();
  return roomData;
}''')
body('失敗時はAPIのdetailを読み取り、読めなければ共通のメッセージを使います。422は入力不正として案内します。fetchは404や503だけで自動的に例外になるわけではないので、response.okの確認が必要です。')
why('理由を返す形式なら、カレンダーで押せなくする判定と送信前のエラー表示に同じ関数を使えます。失敗メッセージも通信側へ集めることで、作成画面と表示画面で共通の扱いにできます。')

begin('B-6｜作成画面を新しく作る理由','新規ファイル｜/rooms/newは、入力とプレビューを担当するページです。','B｜新規ファイルの作成')
source('frontend/app/rooms/new/page.tsx')
why('商品を検索する画面とは入力内容も目的も違うため、ルーム作成用のページを分けました。入力中の値はuseStateで覚え、作成ボタンを押したときだけAPIへ依頼します。')
code('''const [title, setTitle] = useState("");
const [nickname, setNickname] = useState("");
const [budget, setBudget] = useState("");
const [members, setMembers] = useState("");
const [deadline, setDeadline] = useState("");''')
body('左側の名前は現在の値、setで始まる名前は更新用の関数です。空文字は初期値です。useStateだけではDBへ保存されません。数字も、入力中は空欄にできるよう文字列で保持しています。')
h('入力欄と状態を結び付ける')
code('''<input
  name="title"
  value={title}
  onChange={e => setTitle(e.target.value)}
  required
  maxLength={100}
/>''')
body('入力のたびにonChangeが呼ばれ、入力文字がsetTitleへ渡ります。value={title}で、その状態を入力欄の表示へ反映します。requiredは必須、maxLengthは最大文字数です。')
h('プレビューは、保存する前の確認用')
code('''const budgetValue = Number(budget);
const memberValue = Number(members);
if (budgetValue > 0 && memberValue > 0) {
  const perPerson = Math.ceil(budgetValue / memberValue);
  previewPrice = `¥${perPerson.toLocaleString("ja-JP")}`;
}''')
body('Numberで数値へ変換し、Math.ceilで切り上げます。API側でも負担額を計算するため、画面のプレビュー値を保存結果の代わりにはしません。')

begin('B-7｜作成画面のsubmitを順に読む','新規ファイルの中身｜入力確認 → 送信 → 成功なら移動、失敗なら再試行、の順番です。','B｜新規ファイルの作成')
source('frontend/app/rooms/new/page.tsx')
compact_code('''event.preventDefault();
if (submitting.current) {
  return;
}
setError("");
const deadlineError = unavailableDate(deadline);
if (deadlineError !== null) {
  setError(deadlineError);
  return;
}
const roomTitle = title.trim();
const organizerNickname = nickname.trim();
if (roomTitle === "" || organizerNickname === "") {
  setError("ルーム名とニックネームを入力してください。");
  return;
}''')
body('preventDefaultはフォーム標準の再読み込みを止めます。submitting.currentは連続送信を防ぐための値です。入力不正ならsetErrorで表示し、returnで保存依頼に進まず終了します。trimは前後の空白を除きます。')
compact_code('''const roomInput: RoomInput = {
  title: roomTitle,
  nickname: organizerNickname,
  budget_total: budgetValue,
  member_count: memberValue,
  deliver_by: deadline,
};
submitting.current = true;
setSaving(true);
try {
  const createdRoom = await createRoom(roomInput);
  router.push(createdRoom.room_path);
} catch (error) {
  let message = "ルームを作成できませんでした。";
  if (error instanceof Error) {
    message = error.message;
  }
  setError(message);
  submitting.current = false;
  setSaving(false);
}''')
why('APIで保存が成功してから移動し、保存前に成功画面を見せないようにします。失敗時は入力を残して再試行できるようにします。useRefはすぐ確認する送信中フラグ、useStateのsavingはボタン表示の更新に使います。')

begin('B-8｜表示画面を新しく作る理由','新規ファイル｜/rooms/[roomId]で、保存したルームを同じURLから開けるようにしました。','B｜新規ファイルの作成')
source('frontend/app/rooms/[roomId]/page.tsx')
why('作成直後にだけ情報を持つ構成では、再読み込みや後日の再訪に対応できません。URLの番号を使ってAPIから取り直し、保存済み情報を表示するページを用意しました。')
code('''const { roomId } = useParams<{ roomId: string }>();
const [room, setRoom] = useState<Room | null>(null);

async function loadRoom() {
  try {
    const roomData = await getRoom(roomId, controller.signal);
    setRoom(roomData);
  } catch (error) {
    if (controller.signal.aborted) {
      return;
    }
    // 実際のコードでは、ここでエラーメッセージを設定する。
  }
}''')
story.append(table([
['名前・処理','担当'],['useParams / roomId','URLが/rooms/2なら、番号の"2"を取得する。'],['getRoom','APIへ通信して取得する。自分たちで作った関数。'],['setRoom','取得した情報を画面の状態へ入れる。DBやファイルに保存しない。'],['useEffect','画面の表示後やroomIdの変更時に取得を始める。'],['AbortController','画面を離れたときなどに、不要な通信を中止する。'],
],[W*.35,W*.65]))
h('表示は3段階で分ける')
body('① errorがあればエラー画面。② roomがnullなら読み込み中。③ 情報が入ったら予算・人数・受け取り期限などを表示。setRoomによる状態更新で、Reactが表示を切り替えます。URLをコピーする処理もこの画面にあります。')
story.append(note('getRoom＝取得、setRoom＝画面の状態更新、createRoom＝作成の依頼。getやsetという名前そのものがDB操作をするわけではありません。'))

begin('B-9｜DateCalendarを分けた理由','新規ファイル｜受け取り期限の日付選択と、選べない日の表示を担当します。','B｜新規ファイルの作成')
source('frontend/app/rooms/DateCalendar.tsx')
why('日付ボタンの生成や月移動を作成フォーム本体から分けると、入力・送信の流れが読みやすくなります。必要な機能を月表示と選択制限に絞り、追加のカレンダーライブラリは使っていません。')
code('''const monthParts = month.split("-");
const year = Number(monthParts[0]);
const monthNumber = Number(monthParts[1]);
const firstDate = new Date(Date.UTC(year, monthNumber - 1, 1));
const firstWeekday = firstDate.getUTCDay();
const lastDate = new Date(Date.UTC(year, monthNumber, 0));
const daysInMonth = lastDate.getUTCDate();''')
body('Dateの月は0始まりなので、1月なら0を渡します。次の月の0日目で当月の最終日を得ます。月初の曜日までの空欄を置き、その後に日付を1つずつ並べます。')
code('''const reason = unavailableDate(day, today);
const isUnavailable = reason !== null;
const isSelected = day === value;

<button
  type="button"
  disabled={isUnavailable}
  aria-pressed={isSelected}
  onClick={() => onChange(day)}
>
  {dayNumber}
</button>''')
body('reasonがあれば選べない日なので、disabledをtrueにします。onChangeで選んだ日を親の作成画面へ知らせ、親のsetDeadlineで覚えます。valueは親から渡された選択済みの日です。')
body('表示月の範囲も、今日の月から祝日データのある年までに制限しています。日付の最終確認はAPIでも行うため、ボタンを押せなくするだけで保存ルールを守ったことにはしていません。')

begin('B-10｜共通の枠と見た目を作る理由','新規ファイル｜RoomShell.tsxは共通の配置、rooms.cssは配色や幅を担当します。','B｜新規ファイルの作成')
source('frontend/app/rooms/RoomShell.tsx')
code('''type RoomShellProps = {
  children: ReactNode;
  title?: string;
};

<main className="room-main">{children}</main>''')
body('childrenはRoomShellの内側に書かれた各画面の内容です。titleは渡しても渡さなくてもよいルーム名です。作成画面と表示画面で、同じヘッダー・本文の枠・フッターを使います。')
why('ヘッダーを複数画面へコピーすると、見た目を直すたびに何か所も変更する必要があります。共通部分を1つの部品にして、各画面は入力・表示などの本体に集中できるようにしました。')
source('frontend/app/rooms/rooms.css')
body('CSSは色、文字、カード、余白、配置を設定します。.room-appの内側を中心に適用し、既存検索画面へ影響が広がらないようにしています。@mediaでスマートフォン時に縦並びへ切り替えます。')
imgpath=ROOT/'docs/work-log/evidence/2026-11-17-refactor/room-detail-desktop.png'
im=Image(str(imgpath));iw,ih=im.imageWidth,im.imageHeight;im.drawWidth=350;im.drawHeight=350*ih/iw
story.append(im)
story.append(P('11/17の確認画像。APIはダミー応答で、予算・名前もダミー。','small'))

begin('B-11｜schema.sqlを作った理由','新規ファイル｜保存先の表をコードとして残し、どんな項目を持つか共有します。','B｜新規ファイルの作成')
source('db/schema.sql')
why('商品用のproductsはルームの情報を保存する表ではありません。ルームの条件と、所属メンバーを別々に保存し、番号で結び付けるために2テーブルを用意しました。既存商品テーブルは変更していません。')
code('''CREATE TABLE IF NOT EXISTS consultations (
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(100) NOT NULL,
  budget_total INT NOT NULL,
  member_count INT NOT NULL,
  ...
  deliver_by DATE NOT NULL,
  ...
  organizer_id INT NULL,
  ...
  CHECK (budget_total >= 1),
  CHECK (member_count >= 1)
);''')
body('省略記号は説明用で、そのまま実行するSQLではありません。1行が1ルームです。AUTO_INCREMENTは自動の番号、PRIMARY KEYは行の識別、NOT NULLは必須、CHECKは値の条件です。')
code('''CREATE TABLE IF NOT EXISTS consultation_members (
  id INT AUTO_INCREMENT PRIMARY KEY,
  consultation_id INT NOT NULL,
  nickname VARCHAR(30) NOT NULL,
  ...
  UNIQUE KEY uq_room_nickname (consultation_id, nickname),
  FOREIGN KEY (consultation_id)
    REFERENCES consultations(id) ON DELETE CASCADE
);''')
body('1行が1人です。consultation_idで所属ルームへつなぎます。UNIQUEで同じルーム内の同名登録を防ぎ、外部キーで存在するルームとの関連を保ちます。今回は幹事登録に利用しています。')
story.append(note('IF NOT EXISTSは未作成の表を作るだけです。既存の列を更新する仕組みではありません。decide_byなどの列はあっても、今回の画面では未使用です。'))

begin('B-12｜共通の祝日データを作った理由','新規ファイル｜shared/japan-holidays.jsonはプログラムではなく、両方のプログラムが読むデータです。','B｜新規ファイルの作成')
source('shared/japan-holidays.json')
code('''{
  "source": "https://www8.cao.go.jp/chosei/shukujitsu/gaiyou.html",
  "checked_on": "2026-11-15",
  "supported_years": [2026, 2027],
  "holidays": {
    "2026-11-03": "文化の日",
    "2026-11-23": "勤労感謝の日"
  }
}''')
body('これは一部の日付だけを載せた学習用の抜粋です。実ファイルは2026・2027年の国民の祝日・振替休日・国民の休日を収録しています。sourceは出典、checked_onはデータ確認日です。')
why('画面とAPIに別々の一覧を作ると、片方だけの更新で判定が食い違います。小さなJSONを共有することで、どちらも同じ休日を確認できます。必要な年が限られた今回のPoCでは、外部APIへの実行時通信や新しい休日ライブラリを増やさずに済みます。')
story.append(table([
['読む側','使い方'],['画面のlib/rooms.ts','importして休日名・対応年を使う。DateCalendarもこの判定を利用。'],['APIのrooms.py','json.loadsで読み込み、保存前の最終チェックへ使う。'],['Next.jsの設定','frontend外のsharedを参照できるようにする。'],
],[W*.35,W*.65]))
body('一覧方式には、更新が必要という制約があります。他の年はデータを追加するまで指定できません。毎年自動的に正しくなる仕組みではありません。営業日の逆算も、この一覧を置いただけでは実装されません。')
h('「今日」と日付の書式')
body('APIはJST、画面はIntlのAsia/Tokyoを使い、日本時間の今日をそろえます。保存する日付文字列はYYYY-MM-DDです。データを扱う形式と、「2026年11月24日(火)」のような表示形式は区別しています。')

begin('B-13｜test_rooms.pyを作った理由','新規ファイル｜プログラムの変更で、保存や既存検索を壊していないかを確かめます。','B｜新規ファイルの作成')
source('backend/test_rooms.py')
why('画面から正常に1回保存できるだけでは、入力エラーや途中失敗時の動作は分かりません。自動テストで同じ確認を繰り返せるようにし、読みやすく書き換えた後も以前と同じ結果になるかを確認しました。')
code('''with patch("database.get_connection", side_effect=lambda:
           TestConnection(self.filename, fail_on_member=True)):
    response = self.client.post("/api/rooms", json=self.body)
self.assertEqual(response.status_code, 503)
self.assertNotIn("dummy failure", response.text)
self.assertEqual(self.count("consultations"), 0)
self.assertEqual(self.count("consultation_members"), 0)''')
body('幹事登録をわざと失敗させ、ルームも幹事も0件のままであることを確認します。実際のファイルでは同じ内容を1行のwithに記述しています。')
story.append(table([
['使ったもの','理由'],['unittest / unittest.mock','Python標準。確認の実行と、接続先や今日の日付の置き換えに使う。'],['sqlite3 / tempfile','Python標準。一時的なテスト用DBを使い、班のMySQLを変更せずに試す。'],['FastAPI TestClient / httpx','HTTPの依頼に近い形で、アプリのルートを呼んで確認する。[4]'],
],[W*.38,W*.62]))
body('テスト用SQLiteは、アプリ本体の接続先を変更したものではありません。通常は班のAzure MySQLを使います。TestClient用のhttpxは確認用で、この環境には既にありました。新しい本番用ライブラリは追加していません。')
h('確認記録')
body('11/17のAPIテスト11件は成功。保存・再取得、取り消し、不正入力、休日、既存検索などを確認しました。日付判定1,474ケース・通信20ケースも整理前と一致。ビルドと静的チェック、ダミーAPIでのPC・スマートフォン操作も確認しています。これは記録済みの結果で、今回の資料編集で再実行したという意味ではありません。')

begin('復習｜コードを読む順番と選定理由','ファイルごとの知識を、利用者の操作に結び付けて読んでみましょう。','付録')
story.append(table([
['利用者の操作','読む場所','確認すること'],['入力する','new/page.tsxのuseStateとinput','入力文字がどこへ入り、どの表示に使われるか。'],['作成を押す','submit → lib/rooms.tsのcreateRoom','どこで入力を確認し、何をJSONで送るか。'],['保存する','rooms.pyのcreate_room → transaction','3つのSQLを実行する順番と、失敗時の取り消し。'],['表示する','表示画面のloadRoom → getRoom → get_room','URLの番号をどう渡し、DBの何を取得するか。'],['画面を更新','setRoom → roomを使うJSX','取得と状態更新が別であること。'],
],[W*.20,W*.40,W*.40]))
h('ライブラリを選ぶときに説明したいこと')
body('① 既存の講義・配布コードを生かせるか。② 今回必要な機能が本当にあるか。③ 追加の学習・依存を増やす必要があるか。④ テストやエラー確認ができるか。今回の判断は、この4点に沿って「既存構成＋標準機能」を中心にしています。')
h('コードが読みやすくなった点')
code('''const roomData = await getRoom(roomId, controller.signal);
setRoom(roomData);''')
body('取得してから状態を更新する順番を2行に分けました。負担額もmath.ceilにし、返す項目を一つずつ書きました。行数の短さより、処理を追えることを優先しています。')
story.append(note('残す必要がある仕組み：API入力検証、SQLの値の分離、まとめて確定・取り消し、連続送信防止、通信失敗の表示。読みやすくするために、これらを削除したわけではありません。'))
h('今回まだ作っていないもの')
body('メンバー参加操作、共有プロフィール、候補ストック・提出、コンシェルジュ、投票、決定期限、発送・配送の営業日の逆算。今ある列や画面イメージだけを見て、実装済みとは判断しないでください。')

begin('付録｜起動手順・公式資料・参照記録','下のコマンドは、各ターミナルをリポジトリのルートで開いて実行します。既存のDB設定と依存が準備済みの環境向けです。','付録')
h('Windows / PowerShell')
code('''# ターミナル1：API
Set-Location backend
$env:CORS_ORIGINS='http://127.0.0.1:3001,http://localhost:3000'
python -m uvicorn main:app --host 127.0.0.1 --port 8000
# ターミナル2：画面
Set-Location frontend
npm.cmd run dev -- --hostname 127.0.0.1 --port 3001''')
h('macOS')
code('''# ターミナル1：API
cd backend
export CORS_ORIGINS='http://127.0.0.1:3001,http://localhost:3000'
python3 -m uvicorn main:app --host 127.0.0.1 --port 8000
# ターミナル2：画面
cd frontend
npm run dev -- --hostname 127.0.0.1 --port 3001''')
body('既存の同じポートのサーバーは、起動したターミナルでCtrl+Cしてから再起動します。画面：http://127.0.0.1:3001/rooms/new／API確認：http://127.0.0.1:8000/docs。')
h('公式資料（2026-11-17確認）')
for label,url in [
('[1] Next.js：Server and Client Components','https://nextjs.org/docs/app/getting-started/server-and-client-components'),
('[2] FastAPI：Features','https://fastapi.tiangolo.com/features/'),
('[3] PyMySQL：Examples','https://pymysql.readthedocs.io/en/latest/user/examples.html'),
('[4] FastAPI：Testing','https://fastapi.tiangolo.com/tutorial/testing/')]:
    story.append(P(label+'\n'+url,'small'))
story.append(P('ローカル記録：'+(ROOT/'docs/work-log/2026-11-17-room-code-refactor.md').as_posix()+'\n起動手順：'+(ROOT/'docs/room-poc-setup.md').as_posix(),'small'))
story.append(P('分類の根拠：作業中の実ファイル、実装開始前のHEAD、取り込み元origin/main、11/15・11/17の作業記録。技術の性質と、今回その技術を選んだ判断は区別しています。今回の資料編集では、アプリのコード・DB・接続設定は変更していません。','small'))

# ファイルとコード参照が実在し、分類の前提に合うかを確認する。
old_db=subprocess.check_output(['git','show','HEAD:backend/database.py']).decode('utf-8')
assert 'def insert(' not in old_db and 'def transaction(' not in old_db
old_main=subprocess.check_output(['git','show','HEAD:backend/main.py']).decode('utf-8')
assert 'include_router(rooms_router)' not in old_main
old_config=subprocess.check_output(['git','show','origin/main:frontend/next.config.ts']).decode('utf-8')
assert 'turbopack' not in old_config

def footer(c,doc):
    c.saveState();w,hh=A4
    c.setFillColor(RUST);c.setFont('JPBold',8);c.drawString(45,hh-30,'GIFTIA  /  BEGINNER CODE GUIDE - EXPANDED')
    c.setStrokeColor(LINE);c.line(45,37,w-45,37)
    c.setFillColor(MUTED);c.setFont('JP',7.5);c.drawString(45,23,'既存改修・新規作成・選定理由  |  2026-11-17')
    c.drawRightString(w-45,23,str(doc.page));c.restoreState()

doc=SimpleDocTemplate(str(OUT),pagesize=A4,leftMargin=45,rightMargin=45,topMargin=49,bottomMargin=49,
    title='Giftia コード解説・追記版 - 既存改修と新規作成、選定理由',author='Giftia 学習資料')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
reader=PdfReader(OUT);texts=[p.extract_text() for p in reader.pages]
print('PDF:',OUT);print('Expected pages:',len(page_titles),'Actual pages:',len(texts))
for i,t in enumerate(texts,1):print('PAGE',i,'length',len(t),'start',t[100:160].replace('\n',' '))
assert len(texts)==len(page_titles),(len(texts),len(page_titles))
for i,title in enumerate(page_titles):assert title in texts[i],(i+1,title)
assert all(len(t)>250 for t in texts)
for term in ['A-1｜main.py','B-1｜rooms.py','ライブラリ・技術の選定理由','なぜ、この処理の順番にしたか','math.ceil','const roomData = await getRoom']:
    assert term in ''.join(texts),term
(ROOT/'tmp/pdfs/expanded-guide-validation.json').write_text(json.dumps({'pages':len(texts),'titles':page_titles,'parts':parts,'source_ranges':source_checks,'classification_check':'PASS'},ensure_ascii=False,indent=2),encoding='utf-8')
print('Content checks: PASS')
