from pathlib import Path
from xml.sax.saxutils import escape
import json
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Flowable, Image, KeepTogether)
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'output/pdf/Giftia_今回の編集内容とコード解説_初学者向け.pdf'
OUT.parent.mkdir(parents=True,exist_ok=True)
for name,file in [('JP','meiryo.ttc'),('JPBold','meiryob.ttc'),('Mono','msgothic.ttc')]:
 pdfmetrics.registerFont(TTFont(name,'C:/Windows/Fonts/'+file,subfontIndex=0))
INK=colors.HexColor('#2c2335');MUTED=colors.HexColor('#6e6672')
RUST=colors.HexColor('#b7472e');TEAL=colors.HexColor('#2c7270');LINE=colors.HexColor('#e5dacf');PAPER=colors.HexColor('#f7f3ee')
W=A4[0]-90
S={
 'title':ParagraphStyle('title',fontName='JPBold',fontSize=21,leading=30,textColor=INK,spaceAfter=12,wordWrap='CJK'),
 'lead':ParagraphStyle('lead',fontName='JP',fontSize=10,leading=18,textColor=MUTED,spaceAfter=13,wordWrap='CJK'),
 'body':ParagraphStyle('body',fontName='JP',fontSize=9.5,leading=16.8,textColor=INK,spaceAfter=9,wordWrap='CJK'),
 'h':ParagraphStyle('h',fontName='JPBold',fontSize=12,leading=19,textColor=INK,spaceBefore=13,spaceAfter=7,wordWrap='CJK'),
 'small':ParagraphStyle('small',fontName='JP',fontSize=8,leading=13,textColor=MUTED,spaceAfter=7,wordWrap='CJK'),
 'cell':ParagraphStyle('cell',fontName='JP',fontSize=8.4,leading=13.5,textColor=INK,wordWrap='CJK'),
 'cellhead':ParagraphStyle('cellhead',fontName='JPBold',fontSize=8.5,leading=13.5,textColor=INK,wordWrap='CJK'),
 'callout':ParagraphStyle('callout',fontName='JPBold',fontSize=9.4,leading=17,textColor=TEAL,spaceAfter=0,wordWrap='CJK')
}
def P(t,style='body'):return Paragraph(escape(t).replace('\n','<br/>'),S[style])
def table(rows,widths=None):
 data=[[P(str(c),'cellhead' if i==0 else 'cell') for c in r] for i,r in enumerate(rows)]
 t=Table(data,colWidths=widths or [W/len(rows[0])]*len(rows[0]),hAlign='LEFT')
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),PAPER),('VALIGN',(0,0),(-1,-1),'TOP'),
 ('LINEBELOW',(0,0),(-1,0),.7,LINE),('LINEBELOW',(0,1),(-1,-1),.35,LINE),
 ('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),
 ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
 return t

def note(t):
 q=Table([[P(t,'callout')]],colWidths=[W]);q.setStyle(TableStyle([
 ('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#edf3ef')),('BOX',(0,0),(-1,-1),.5,colors.HexColor('#ceded3')),
 ('LEFTPADDING',(0,0),(-1,-1),12),('RIGHTPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10)]));return q

class Code(Flowable):
 def __init__(self,text):
  super().__init__();self.lines=text.strip('\n').splitlines();self.width=W
  self.size=8.4
  longest=max(pdfmetrics.stringWidth(x,'Mono',self.size) for x in self.lines)
  if longest>W-26:self.size*= (W-26)/longest
  assert self.size>=7.3, f'Code line too long: {max(self.lines,key=len)}'
  self.leading=self.size*1.5;self.height=len(self.lines)*self.leading+24
  self.spaceBefore=4;self.spaceAfter=11
 def draw(self):
  c=self.canv;c.setFillColor(PAPER);c.roundRect(0,0,self.width,self.height,7,fill=1,stroke=0)
  c.setFillColor(INK);c.setFont('Mono',self.size)
  y=self.height-13-self.size
  for line in self.lines:c.drawString(13,y,line);y-=self.leading

class Architecture(Flowable):
 def __init__(self):super().__init__();self.width=W;self.height=96
 def draw(self):
  c=self.canv;bw=145;gap=(W-3*bw)/2
  for i,(title,sub,last) in enumerate([('画面','Next.js / React','入力・表示'),('API','FastAPI / Python','入力確認・処理'),('DB','Azure MySQL','データを保存')]):
   x=i*(bw+gap);c.setFillColor(PAPER if i!=1 else INK);c.roundRect(x,17,bw,73,8,fill=1,stroke=0)
   c.setFillColor(INK if i!=1 else colors.white);c.setFont('JPBold',12);c.drawCentredString(x+bw/2,68,title)
   c.setFont('JP',8.2);c.drawCentredString(x+bw/2,48,sub);c.drawCentredString(x+bw/2,32,last)
   if i<2:
    x1=x+bw+3;x2=x+bw+gap-4;c.setStrokeColor(RUST);c.line(x1,56,x2,56);c.line(x2-4,59,x2,56);c.line(x2-4,53,x2,56)

story=[];page_titles=[]
def page(title,lead):
 if story:story.append(PageBreak())
 page_titles.append(title);story.extend([P(title,'title'),P(lead,'lead')])
def body(t):story.append(P(t))
def h(t):story.append(P(t,'h'))
def code(t):story.append(Code(t))
def source(rel):
 assert (ROOT/rel).is_file(),rel
 story.append(P('参照：'+(ROOT/rel).as_posix(),'small'))
def excerpt(rel,start,end):
 lines=(ROOT/rel).read_text(encoding='utf-8').splitlines()
 a=next(i for i,s in enumerate(lines) if start in s)
 b=next((i for i in range(a+1,len(lines)) if end in lines[i]),len(lines))
 return '\n'.join(lines[a:b]).rstrip()

page('Giftia 今回の編集内容とコード解説','初学者向け学習ガイド｜2026-11-15時点の実装\n目標：ルームを作って保存し、同じURLで再表示するまでを自分の言葉で説明する。')
body('今回追加した中心の機能は「ギフトルームの作成・保存・表示」です。商品を探す画面に加えて、総予算・参加予定人数・受け取り期限・幹事を記録できるようにしました。')
story.append(table([['以前の状態','今回行った変更'],['商品検索が中心。書き込み関数は添付ファイルにある状態。','検索を残し、ルーム用の画面・API・DBテーブルを追加。'],['画面だけで入力内容を覚えても、再読み込みで失われる。','MySQLへ保存し、ルーム番号から取り直して表示する。']], [W*.43,W*.57]))
h('全体は「画面 → API → DB」の3つに分担')
story.append(Architecture())
body('画面とAPIは手元のPCで動き、DBは班のAzure MySQLを使います。画面からDBへ直接接続せず、APIを通して読み書きします。結果はDB → API → 画面の順に返ります。')
story.append(note('今回できること：ルーム作成、幹事の同時登録、予算・人数・受け取り期限の保存、負担額の表示、保存後の再表示。'))
h('入力から再表示までの流れ')
body('入力 → 画面で確認 → POSTで作成依頼 → APIで再確認 → ルーム・幹事を保存して確定 → 結果を返す → ルーム画面へ移動 → GETで情報を取り直す → 表示。途中で失敗した場合は、保存の取り消しやエラー表示へ進みます。')
h('読む順番')
body('2ページ：ファイルの地図／3〜5ページ：画面と通信／6〜7ページ：入力・日付の確認／8〜9ページ：DB保存／10〜12ページ：負担額と再表示／13〜15ページ：見た目・テスト・起動と復習。')
body('コードは現行ファイルを基準に、必要な部分を抜粋・改行・簡略化しています。学習用の抜粋をそのままファイル全体に上書きしないでください。')
story.append(P('未実装：メンバー参加操作、共有プロフィール、候補提出、コンシェルジュ、投票、決定期限、営業日の逆算。','small'))

page('01｜ファイルの地図','同じ「ルーム」という名前でも、画面側とAPI側では担当が違います。まずは役割を確認しましょう。')
body('作業フォルダー：'+ROOT.as_posix()+'\n以下のファイル名は、このフォルダーからの位置を示します。')
story.append(table([
 ['ファイル','変更内容・役割'],
 ['frontend/app/rooms/new/page.tsx','新規：入力フォームと作成ボタン。画面側の処理の入口。'],
 ['frontend/lib/rooms.ts','新規：APIとの通信、日付の確認、表示用の型。'],
 ['frontend/app/rooms/DateCalendar.tsx','新規：土日祝日などを選べないカレンダー。'],
 ['frontend/app/rooms/[roomId]/page.tsx','新規：URLの番号で情報を取得し、保存内容を表示。'],
 ['backend/rooms.py','新規：ルーム用API、入力検証、保存・取得・負担額計算。'],
 ['backend/database.py','既存へ追加：添付のinsert・execute・transactionを取り込んだ。'],
 ['backend/main.py','既存を変更：ルーム用APIを登録。CORSでPOSTも許可。'],
 ['db/schema.sql','新規：ルーム・メンバーを保存する2テーブル。'],
 ['shared/japan-holidays.json','新規：画面とAPIが共通で使う2026・2027年の祝日データ。'],
 ['frontend/app/rooms/RoomShell.tsx / rooms.css','新規：共通ヘッダー、枠、配色、スマートフォン対応。'],
 ['frontend/app/page.tsx / ResultCard.tsx、frontend/lib/api.ts','origin/mainの整備済み検索画面を取り込んだ。検索画面にルーム作成へのリンクを追加。'],
 ['frontend/app/layout.tsx / globals.css','起動構成を取り込んだ。共通のHTMLと基本的な見た目。'],
 ['frontend/package.json / package-lock.json / tsconfig.json / eslint.config.mjs','不足していた起動・依存・型チェック・静的チェックの構成をorigin/mainから取り込んだ。'],
 ['frontend/next.config.ts','起動構成を取り込み、共通の祝日JSONを参照できる範囲を設定。'],
 ['backend/test_rooms.py','新規：保存・取得・取り消し・不正入力・既存検索の確認。'],
 ],[W*.47,W*.53]))
body('今回追加・編集したプログラム17ファイルの先頭に、日本語で役割の説明を付けました。JSONには通常のコメント構文がないため、同じ書き方では追加していません。')

page('02｜入力した値を画面が覚える','対象：ルーム作成画面。まずは「画面の中で覚える」と「DBに保存する」を分けて考えます。')
source('frontend/app/rooms/new/page.tsx')
code('''const [title, setTitle] = useState("");
const [budget, setBudget] = useState("");
const [members, setMembers] = useState("");
const [deadline, setDeadline] = useState("");''')
body('useStateは、画面で変化する値を覚えるReactの仕組みです。titleは現在の値、setTitleは値を更新する関数、空文字の "" は最初の状態を表します。更新するとReactが表示を更新します。')
code('''<input
  name="title"
  value={title}
  onChange={e => setTitle(e.target.value)}
  required
  maxLength={100}
/>''')
story.append(table([['コード','意味'],['value={title}','入力欄の表示をtitleの値に合わせる。'],['onChange={...}','入力欄の内容が変わったときに実行する。'],['e.target.value','利用者がその時点で入力した文字。'],['setTitle(...)','新しい文字を画面の状態に入れる。'],['required / maxLength','ブラウザー側で必須・最大文字数を確認する。']],[W*.36,W*.64]))
h('数字の入力欄でも、画面の状態は文字列')
body('budgetやmembersは、入力中に空欄にもできるよう文字列で保持しています。APIへ送るときはNumber(budget)のように数値へ変換します。')
body('入力欄やボタンをHTMLに似た形で記述する部分をJSXと呼びます。{title}のような波括弧の中にはJavaScriptの値や式を書けます。')
story.append(note('useStateで覚えた情報は画面側の状態です。この段階ではDBに保存されていません。'))

page('03｜作成ボタンを押したときの流れ','対象：submit関数。入力を確認してから送信し、成功と失敗で処理を分けています。')
source('frontend/app/rooms/new/page.tsx')
code('''async function submit(event) {
  event.preventDefault();
  if (submitting.current) return;
  setError("");

  const reason = unavailableDate(deadline);
  if (reason) { setError(reason); return; }
  if (!title.trim() || !nickname.trim()) {
    setError("ルーム名とニックネームを入力してください。");
    return;
  }
  submitting.current = true;
  setSaving(true);
  try {
    const room = await createRoom({
      title: title.trim(), nickname: nickname.trim(),
      budget_total: Number(budget),
      member_count: Number(members), deliver_by: deadline,
    });
    router.push(room.room_path);
  } catch (err) {
    setError(err instanceof Error ? err.message : "作成できませんでした。");
    submitting.current = false;
    setSaving(false);
  }
}''')
story.append(table([['処理','なぜ必要か'],['preventDefault()','フォーム標準のページ移動を止め、自分たちの送信処理を行う。'],['setError → return','エラーを表示し、保存依頼に進まず関数を終える。'],['trim() / Number()','前後の空白を除く。予算・人数を文字列から数値へ変える。'],['useRef / useState','submitting.currentで連続送信を防ぎ、savingでボタン表示を変える。'],['try / catch','成功ならルーム画面へ移動。失敗なら入力を残して再試行できるようにする。']],[W*.32,W*.68]))
body('asyncは非同期の関数、awaitは処理の結果を待つ書き方です。router.pushは表示先のURLを変えます。画面を移動する処理と、DBへ保存する処理は別です。')

page('04｜画面からAPIへ依頼を送る','対象：frontend/lib/rooms.ts。通信処理を画面から分け、作成・取得の呼び出し口をまとめました。')
source('frontend/lib/rooms.ts')
code('''const response = await fetch(`${API}/api/rooms`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(input),
});
const room = await responseRoom(response);''')
body('この抜粋は、実装の入れ子になったawaitを2段階に書き分けたものです。画面は入力を送り、APIから保存の結果が返るのを待ちます。')
story.append(table([['記述','意味'],['POST /api/rooms','新しいルームを作成してください、という依頼。'],['JSON.stringify(input)','JavaScriptのオブジェクトを、送信用のJSON文字列にする。'],['Content-Type','送る本文がJSONであることをAPIへ伝える。'],['await fetch(...)','HTTPレスポンスが利用可能になるまで待つ。本文の読み取り完了とは別。'],['responseRoom(response)','成功かを確認し、成功ならresponse.json()で本文を読み取り解析する。']],[W*.34,W*.66]))
h('送る情報の例（学習用のダミー）')
code('''{
  "title": "送別ギフト",
  "budget_total": 4500,
  "member_count": 3,
  "deliver_by": "2026-11-24",
  "nickname": "ダミー幹事"
}''')
body('APIはこの情報を受け取り、Pythonの入力モデルで確認します。画面側のRoomInputはTypeScriptの型で、開発中の書き間違いを見つける補助です。外部から来る入力の実行時チェックはAPI側でも必要です。')
story.append(note('fetchはAPIに依頼する処理です。ブラウザーからMySQLへ直接接続しているわけではありません。'))

page('05｜APIが入力を確認する','対象：RoomCreate。保存処理の前に「何を受け取り、何を許可するか」を決めます。')
source('backend/rooms.py')
code(excerpt('backend/rooms.py','class RoomCreate(BaseModel):','    @field_validator'))
body('BaseModelはPydanticの入力モデルです。FastAPIは、届いたJSONをこのモデルに当てはめます。条件に合わない場合、create_roomの保存処理に進まず、入力エラーとして返します。')
story.append(table([['記述','今回の意味'],['str / int / date','文字列・整数・日付として受け取る。'],['min_length / max_length','名前を空欄にしない。保存できる長さに制限する。'],['strict=True','予算や人数に整数を要求する。文字列や真偽値などを安易に整数へ変換しない。'],['ge=1 / le=2147483647','1以上、MySQLの符号付きINTに収まる範囲にする。'],['str_strip_whitespace=True','名前などの前後の空白を取り除く。'],['extra="forbid"','定義していない入力項目を受け付けない。']],[W*.41,W*.59]))
h('日付は専用の確認関数でもチェック')
body('field_validatorでdeliver_byを確認します。最初にYYYY-MM-DD形式の正しい日付かを確認し、その後で過去日・土日祝日でないかを確認します。日付らしい文字列なら何でも通す処理にはしていません。')
h('返すデータの形も決める')
body('RoomCreateは受け取る形、Roomは返す形です。@router.postのresponse_model=Roomにより、ルーム番号や負担額など、画面へ返す項目の形を定めています。')
story.append(note('画面の入力制限だけでは不十分です。APIへ直接送られた入力も、保存する前に確認します。'))

page('06｜土日祝日を選べなくする','対象：カレンダー、日付確認関数、共通の祝日JSON。画面とAPIの両方で同じ条件を確認します。')
source('backend/rooms.py')
code('''def validate_deadline(value, today=None):
    if value.year not in CALENDAR["supported_years"]:
        raise ValueError("対応している年を選んでください")
    if value < (today or today_in_japan()):
        raise ValueError("今日以降を選んでください")
    if value.weekday() >= 5 or value.isoformat() in CALENDAR["holidays"]:
        raise ValueError("土日祝日は指定できません")
    return value''')
body('value.weekday()はPythonでは月曜0〜日曜6なので、5以上が土日です。isoformat()は日付を2026-11-24のような文字列にします。祝日の一覧にその日があれば拒否します。')
source('frontend/app/rooms/DateCalendar.tsx')
code('''const reason = unavailableDate(day, today);

<button
  type="button"
  disabled={!!reason}
  onClick={() => onChange(day)}
>
  {i + 1}
</button>''')
body('unavailableDateは、選べない理由があれば文字列、問題がなければnullを返します。!!reasonは値をtrue/falseに変換し、理由がある日にはdisabled=trueを設定します。onChangeは選んだ日を親の作成画面へ知らせます。')
story.append(table([['確認する場所','担当'],['画面','選べない日を薄くし、押せないようにする。送信直前にも確認する。'],['API','直接送られた日付も検証し、不正な日付を保存しない。'],['共通データ','shared/japan-holidays.jsonを両方で参照する。']],[W*.25,W*.75]))
body('「今日」は日本時間で判定します。日本の祝日・振替休日・国民の休日に対応しています。現行の祝日データは2026・2027年分で、他の年は更新するまで指定できません。営業日の逆算は今回まだ実装していません。')
source('shared/japan-holidays.json')

page('07｜DBに何を保存するか','対象：schema.sql。テーブルは表、行は1件のデータ、列は項目と考えると読みやすくなります。')
source('db/schema.sql')
story.append(table([['テーブル','1行に保存するもの'],['consultations','1つのルーム。名前・総予算・参加予定人数・受け取り期限・幹事の番号など。'],['consultation_members','1人のメンバー。所属ルームの番号・ニックネームなど。今回のAPIでは幹事を登録。']],[W*.36,W*.64]))
h('学習用の保存イメージ')
story.append(table([['ルームid','title','budget_total','member_count','organizer_id'],['1','送別ギフト','4500','3','1']],[62,137,105,103,W-407]))
story.append(Spacer(1,10))
story.append(table([['メンバーid','consultation_id','nickname'],['1','1','ダミー幹事']],[100,150,W-250]))
body('consultation_members.consultation_idが、どのルームのメンバーかを表します。consultations.organizer_idには、幹事として登録したメンバーのidを記録します。')
code('''id INT AUTO_INCREMENT PRIMARY KEY,
budget_total INT NOT NULL,
member_count INT NOT NULL,
deliver_by DATE NOT NULL,
CHECK (budget_total >= 1),
CHECK (member_count >= 1)''')
story.append(table([['SQLの記述','意味'],['PRIMARY KEY / AUTO_INCREMENT','各行を識別する番号を、自動で付ける。'],['INT / VARCHAR / DATE','整数・長さを指定した文字列・日付を保存する型。'],['NOT NULL / CHECK','必須の値や、DB側でも守る値の条件を指定する。'],['FOREIGN KEY','存在するルームにメンバーを結び付ける。'],['UNIQUE KEY','同じルームで同じニックネームを重複登録しない。']],[W*.41,W*.59]))
body('IF NOT EXISTSは表がなければ作り、既存の列は更新しません。decide_byは今回の画面では未使用です。参加予定人数と参加済み人数は別です。')

page('08｜関連する保存をまとめて確定する','対象：ルーム作成APIとtransaction関数。ルームだけ残り、幹事がいない状態を防ぎます。')
source('backend/rooms.py')
body('create_roomでは、同じトランザクションの中で次の3つを実行します。SQL中の値はすべて%sの位置へ、別の引数として渡しています。')
code('''with transaction() as cur:
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
    )''')
body('INSERTは行を追加し、UPDATEは行を更新します。cur.lastrowidで直前に追加した行の番号を取得し、ルームと幹事を結び付けています。curはSQLを実行するための窓口で、カーソルと呼びます。')
source('backend/database.py')
code('''try:
    with conn.cursor() as cur:
        yield cur
    conn.commit()
except Exception:
    conn.rollback()
    raise
finally:
    conn.close()''')
body('yield curの間に呼び出し元の3つのSQLを実行します。成功すればcommitで確定し、途中で例外が起きればrollbackで取り消してraiseで失敗を伝えます。finallyでは成功・失敗にかかわらず接続を閉じます。')
story.append(note('SQLの命令と値を分ける%sは、値をSQLの命令として解釈させないためです。保存を確定する役割はcommitが担当します。'))

page('09｜返す情報を整え、負担額を計算する','対象：to_roomとDB共通関数。DBの行に、画面で必要な情報を加えて返します。')
source('backend/rooms.py')
code(excerpt('backend/rooms.py','def to_room(row: dict) -> Room:','def storage_unavailable'))
body('rowは項目名と値の組になった辞書です。**rowは、その辞書の項目をRoomにまとめて渡す書き方です。そこへ計算した負担額と、表示先のURLを加えています。')
h('正の整数の割り算を切り上げる')
code('''(budget_total + member_count - 1) // member_count

# 総予算4501円、3人の場合
(4501 + 3 - 1) // 3
4503 // 3
1501''')
body('//はPythonの切り下げる割り算です。予算・人数が正の整数なので、先に人数−1を足すと端数を切り上げられます。画面の入力中プレビューはMath.ceilで同じ計算を行います。実際の集金・支払いは行いません。')
h('DB共通関数の使い分け')
story.append(table([['関数','役割','今回のルーム処理'],['fetch_all','SELECTを実行し、結果の行を返す。','取得APIで使用。'],['insert','1つのINSERTを確定し、追加したidを返す。','添付から取り込み済み。今回の作成はtransactionを使用。'],['execute','UPDATE・DELETEを確定し、影響した行数を返す。','取り込み済み。行数0は、対象がない場合だけでなく値が変わらない場合もある。'],['transaction','複数のSQLを一緒に確定・取り消しする。','ルームと幹事の同時保存で使用。']],[W*.2,W*.37,W*.43]))
body('room_pathは、たとえば/rooms/1です。末尾の番号が、あとで同じルームを探すための手掛かりになります。')

page('10｜getとsetを区別する','今回いちばん押さえたい点：情報の取得、画面の状態更新、DB保存は別の処理です。')
source('frontend/app/rooms/[roomId]/page.tsx')
code('''const [room, setRoom] = useState<Room | null>(null);

getRoom(roomId).then(setRoom);''')
story.append(table([['名前','今回の役割'],['room','画面が現在覚えているルーム情報。最初はnull。'],['getRoom(roomId)','APIへ通信し、その番号のルーム情報を取得する。'],['setRoom(data)','取得した情報を画面の状態に入れ、Reactの表示更新につなげる。']],[W*.31,W*.69]))
body('getRoomは自分たちで定義した関数です。setRoomはuseStateが返す更新用の関数に付けた名前です。getやsetという名前だけで、自動的にDB操作が行われるわけではありません。')
h('then(setRoom)を書き広げると')
code('''getRoom(roomId).then((data) => {
  setRoom(data);
});''')
body('thenは、非同期の取得が成功したあとに実行する処理を登録します。dataには、取得したルーム情報が入ります。ここではそれをsetRoomへ渡しています。')
h('表示は状態によって切り替わる')
code('''!room
  ? <p>ルームを読み込んでいます…</p>
  : <h1>{room.title}</h1>''')
body('最初のroomはnullなので、!roomはtrueになり、読み込み中の文言を表示します。取得後はroomに情報が入り、ルーム名の表示に切り替わります。?と:は、条件によって値を選ぶ書き方です。')
story.append(note('setRoomはファイル保存やDB保存をしません。再読み込み後は画面の状態が初期化されるため、getRoomで保存済み情報を取り直します。'))

page('11｜URLの番号で取得し、再表示する','対象：ルーム表示画面、getRoom通信関数、GETのAPI。作成した情報をあとから開き直す流れです。')
source('frontend/app/rooms/[roomId]/page.tsx')
code('''const { roomId } = useParams<{ roomId: string }>();

useEffect(() => {
  const controller = new AbortController();
  getRoom(roomId, controller.signal).then(setRoom).catch(err => {
    if (!controller.signal.aborted) {
      setError(err instanceof Error ? err.message : "読み込めませんでした。");
    }
  });
  return () => controller.abort();
}, [roomId]);''')
body('ルートの[roomId]は変わる部分です。/rooms/1ならroomIdは文字列の"1"になります。useEffectは画面の表示後やroomIdが変わったときに取得を始めます。AbortControllerは画面を離れるなどして不要になった通信を中止します。')
source('frontend/lib/rooms.ts')
body('getRoomはGET /api/rooms/1を呼びます。GETは取得の依頼です。encodeURIComponentでURLに値を組み込み、cache: "no-store"でこの取得のキャッシュ利用を避けています。')
source('backend/rooms.py')
code('''@router.get("/{room_id}", response_model=Room)
def get_room(room_id: Annotated[int, ApiPath(ge=1, le=2147483647)]):
    rows = fetch_all(
        """SELECT c.id AS room_id, c.title, c.budget_total,
                  c.member_count, c.deliver_by,
                  m.nickname AS organizer_nickname
           FROM consultations c
           JOIN consultation_members m
             ON m.id = c.organizer_id AND m.consultation_id = c.id
           WHERE c.id = %s""",
        (room_id,),
    )
    if not rows:
        raise HTTPException(404, "ルームが見つかりません。URLを確認してください")
    return to_room(rows[0])''')
body('prefixの/api/roomsと/{room_id}が合わさってURLになります。SELECTは取得、JOINはルームと幹事の表を結び付ける処理です。WHEREで番号を指定します。(room_id,)の末尾のカンマは、要素が1つのタプルを作るためです。')
story.append(P('抜粋ではDB接続エラー処理を省略。実装は接続失敗時に503を返し、内部の接続情報は画面へ出しません。','small'))

page('12｜見た目と共通部品を整える','対象：RoomShell・rooms.css・既存検索の入口。見た目の整理と、データ処理の追加は分けて考えます。')
source('frontend/app/rooms/RoomShell.tsx')
code('''return <RoomShell>
  <h1>ギフトルームをつくる</h1>
  {/* この中に、それぞれの画面の内容を書く */}
</RoomShell>;''')
body('RoomShellは共通のヘッダー・本文の枠・フッターを用意します。挟まれた内容をchildrenとして受け取り、同じ枠の中へ表示します。各画面でヘッダーを何度も書く必要がなくなります。')
source('frontend/app/rooms/rooms.css')
body('CSSは配色、文字の大きさ、余白、カードの形などを担当します。画面幅が狭いときは@mediaで横並びを縦並びへ切り替えます。新しいスタイルは.room-appの中を中心に適用しています。')
imgpath=ROOT/'docs/work-log/evidence/2026-11-15-room-poc/room-detail-mysql-desktop.png'
assert imgpath.is_file()
im=Image(str(imgpath));iw,ih=im.imageWidth,im.imageHeight;im.drawWidth=400;im.drawHeight=400*ih/iw
story.append(im)
story.append(P('実MySQLへの保存後の確認画像。ルーム名・幹事は動作確認用のダミーです。','small'))
body('既存の検索画面には「みんなで贈るルームを作る」のリンクを追加しました。検索処理の呼び出し口は引き続きsearchGiftsです。各プログラムの1行目には、役割を説明する日本語コメントも追加しました。')

page('13｜API登録・接続許可・テスト','新しい関数を書くだけでなく、APIの入口への登録と、既存機能を壊していないかの確認も行いました。')
source('backend/main.py')
code('''from rooms import router as rooms_router

app.include_router(rooms_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)''')
body('include_routerで、rooms.pyにまとめたAPIをアプリへ登録しました。CORSでは、画面とAPIの場所が異なる場合に、許可する画面のURLとGET・POSTをAPI側から伝えます。実際に制限を適用するのはブラウザーです。CORSはログイン機能ではありません。')
body('接続情報はAPI側の環境変数から使い、ブラウザーへ配りません。NEXT_PUBLIC_API_URLは画面へ配られるAPIの場所なので、DBのパスワードなどは入れません。環境ファイルはこの資料に掲載していません。')
source('frontend/next.config.ts')
body('起動に必要なNext.js構成を既存のorigin/mainから取り込み、turbopack.rootをリポジトリ側へ設定しました。frontendの外にあるsharedの祝日JSONを読み込むためです。')
source('backend/test_rooms.py')
story.append(table([['確認したこと','方法・結果'],['API自動テスト11件','保存・再取得、失敗時の取り消し、休日・不正入力、SQLの値の分離、既存検索を確認。成功記録あり。'],['テスト用DB','SQLiteをテスト内だけで使う。通常のアプリのDBをSQLiteに変更したわけではない。'],['実際の保存','画面 → FastAPI → 班のAzure MySQLへダミールームと幹事を保存。再読み込みで再取得。'],['画面の確認','PC・スマートフォン幅390pxを確認。保存失敗時の入力保持も確認。'],['ビルド・静的チェック','npm run build、npm run lintの成功記録あり。']],[W*.27,W*.73]))
story.append(P('実装時の確認記録：'+(ROOT/'docs/work-log/2026-11-15-room-poc.md').as_posix(),'small'))

page('14｜起動・復習のしかた','まず画面で操作し、次に同じ流れのコードを追うと、役割と処理が結び付きます。')
body('再起動する場合は、同じポートのサーバーを終了してから実行してください。下のコマンドは、各ターミナルをリポジトリのルートで開いて使います。DBの既存接続設定と依存パッケージが準備済みの環境向けです。')
h('Windows / PowerShell：ターミナル1でAPI、2で画面')
code('''# ターミナル1
Set-Location backend
$env:CORS_ORIGINS='http://127.0.0.1:3001,http://localhost:3000'
python -m uvicorn main:app --host 127.0.0.1 --port 8000

# ターミナル2
Set-Location frontend
npm.cmd run dev -- --hostname 127.0.0.1 --port 3001''')
h('macOS：ターミナル1でAPI、2で画面')
code('''# ターミナル1
cd backend
export CORS_ORIGINS='http://127.0.0.1:3001,http://localhost:3000'
python3 -m uvicorn main:app --host 127.0.0.1 --port 8000

# ターミナル2
cd frontend
npm run dev -- --hostname 127.0.0.1 --port 3001''')
body('画面：http://127.0.0.1:3001/rooms/new\nAPIの操作確認：http://127.0.0.1:8000/docs\nSwaggerではPOST /api/roomsで作成し、GET /api/rooms/{room_id}で取得できます。確認には実名などを使わず、ダミー値を使ってください。')
h('自分の言葉で説明できるか、確認する')
body('① useStateで覚える値と、DBに保存した値はどう違うか。\n② getRoomとsetRoomは、それぞれ何をするか。\n③ なぜ画面だけでなくAPIでも土日祝日を確認するか。\n④ 幹事登録で失敗したとき、ルーム登録はどうなるか。\n⑤ 再読み込み後、どこから情報を取り直すか。')
story.append(note('読む順番：作成画面のsubmit → 通信のcreateRoom → APIのcreate_room → DBのtransaction。取得は表示画面のuseEffect → getRoom → APIのget_room → setRoomです。'))
story.append(P('起動手順の詳細：'+(ROOT/'docs/room-poc-setup.md').as_posix()+'\n参照コード・記録の確認日：2026-11-15。本資料の作成ではアプリやDBの機能変更は行っていません。','small'))


def footer(c,doc):
 c.saveState();w,hh=A4
 c.setFillColor(RUST);c.setFont('JPBold',8);c.drawString(45,hh-30,'GIFTIA  /  BEGINNER CODE GUIDE')
 c.setStrokeColor(LINE);c.line(45,37,w-45,37)
 c.setFillColor(MUTED);c.setFont('JP',7.7);c.drawString(45,23,'ルーム作成・保存・表示を理解する  |  2026-11-15')
 c.drawRightString(w-45,23,str(doc.page));c.restoreState()

doc=SimpleDocTemplate(str(OUT),pagesize=A4,leftMargin=45,rightMargin=45,topMargin=49,bottomMargin=49,
 title='Giftia 今回の編集内容とコード解説 - 初学者向け',author='Giftia 学習資料')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
r=PdfReader(OUT)
texts=[p.extract_text() for p in r.pages]
print('PDF:',OUT)
print('Page count:',len(r.pages))
for i,t in enumerate(texts,1):
 print('PAGE',i,'text_length',len(t),'start',t[:80].replace('\n',' '))
# 各章を1ページに配置し、コードや説明が意図せず次ページへ流れていないかを確認。
assert len(r.pages)==len(page_titles),(len(r.pages),len(page_titles))
for i,title in enumerate(page_titles):
 assert title in texts[i],(i+1,title)
assert 'setRoomはファイル保存やDB保存をしません' in ''.join(texts)
assert all(len(t)>200 for t in texts)
(ROOT/'tmp/pdfs/guide-validation.json').write_text(json.dumps({'pages':len(r.pages),'page_titles':page_titles,'checks':['all expected chapters on intended pages','no blank pages','get/set explanation present']},ensure_ascii=False,indent=2),encoding='utf-8')
print('Content checks: PASS')

