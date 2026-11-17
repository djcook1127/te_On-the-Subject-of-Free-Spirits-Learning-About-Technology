from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'output/pdf/Giftia_コード理解チェック_問題と解答.pdf'
for name,file in [('JP','meiryo.ttc'),('JPBold','meiryob.ttc'),('JPMono','msgothic.ttc')]:
 pdfmetrics.registerFont(TTFont(name,'C:/Windows/Fonts/'+file,subfontIndex=0))
INK=colors.HexColor('#2c2335'); MUTED=colors.HexColor('#746a77'); ACCENT=colors.HexColor('#ae472f'); LINE=colors.HexColor('#e4d8cc')
styles={
 'title':ParagraphStyle('title',fontName='JPBold',fontSize=20,leading=29,textColor=INK,spaceAfter=10),
 'subtitle':ParagraphStyle('subtitle',fontName='JP',fontSize=9,leading=15,textColor=MUTED,spaceAfter=15,wordWrap='CJK'),
 'h':ParagraphStyle('h',fontName='JPBold',fontSize=12,leading=19,textColor=INK,spaceBefore=13,spaceAfter=8,wordWrap='CJK'),
 'body':ParagraphStyle('body',fontName='JP',fontSize=9.2,leading=16,textColor=INK,spaceAfter=7,wordWrap='CJK'),
 'choice':ParagraphStyle('choice',fontName='JP',fontSize=9,leading=15,textColor=INK,leftIndent=18,firstLineIndent=-18,spaceAfter=5,wordWrap='CJK'),
 'small':ParagraphStyle('small',fontName='JP',fontSize=8,leading=13,textColor=MUTED,spaceAfter=6,wordWrap='CJK'),
 'code':ParagraphStyle('code',fontName='JPMono',fontSize=8.5,leading=12,textColor=INK,backColor=colors.HexColor('#f4efe9'),borderPadding=10,spaceBefore=7,spaceAfter=13),
}
def P(text,style='body'):return Paragraph(escape(text).replace('\n','<br/>'),styles[style])
def C(text):return Preformatted(text,styles['code'])
def question(num,title,code,prompt,choices):
 out=[P(f'第{num}問　{title}','h'),C(code),P(prompt)]
 for letter,text in zip('ABCDE',choices):out.append(P(f'{letter}.  {text}','choice'))
 return out

def footer(c,doc):
 c.saveState();w,h=A4
 c.setFillColor(ACCENT);c.setFont('JPBold',8);c.drawString(45,h-30,'GIFTIA  /  CODE REVIEW QUIZ')
 c.setStrokeColor(LINE);c.line(45,37,w-45,37)
 c.setFillColor(MUTED);c.setFont('JP',8);c.drawString(45,23,'ルーム作成・保存・表示のコード理解チェック')
 c.drawRightString(w-45,23,str(doc.page));c.restoreState()

story=[P('Giftia コード理解チェック','title'),P('問題編｜全5問・各5択。正しいものを1つ選んでください。\n今回作成したルーム機能が題材です。コードは説明に必要な部分を抜粋・省略しています。答えと解説は4ページにあります。','subtitle')]
story+=question(1,'入力すると、なぜ画面の表示が変わる？','''const [title, setTitle] = useState("");

<input
  value={title}
  onChange={e => setTitle(e.target.value)}
/>''','入力欄に「送別ギフト」と入力したとき、何が起きますか？',[
 'titleは空文字のままで、DBだけが更新される。',
 'setTitleが呼ばれ、titleが更新されて画面に反映される。',
 'useStateが入力内容をMySQLへ保存する。',
 '入力するたびに、新しいルームが作成される。',
 'ページ全体が再読み込みされる。'])
story.append(Spacer(1,12))
story+=question(2,'このreturnには、どんな役割がある？','''const reason = unavailableDate(deadline);

if (reason) {
  setError(reason);
  return;
}

const room = await createRoom(...);''','unavailableDateが「今日以降を選んでください」という文字列を返した場合、どうなりますか？',[
 'エラーを表示したあと、ルーム作成も実行する。',
 '受け取り期限を自動的に明日へ変更する。',
 'エラーを表示し、この処理ではルーム作成へ進まない。',
 'DBに保存したルームを削除する。',
 'returnによって、エラーメッセージをDBに保存する。'])
story+=[PageBreak(),P('問題編｜保存と計算','title')]
story+=question(3,'途中で失敗したとき、何が残る？','''with transaction() as cur:
    cur.execute("INSERT INTO consultations ...", ...)
    room_id = cur.lastrowid

    cur.execute("INSERT INTO consultation_members ...", ...)

    cur.execute(
        "UPDATE consultations SET organizer_id = %s WHERE id = %s",
        (organizer_id, room_id),
    )''','このtransaction()は、すべて成功したら保存を確定し、例外が起きたら取り消す仕組みです。2つ目のSQLで例外が起きた場合、どうなりますか？',[
 '1つ目のルーム登録だけが確定する。',
 '2つ目のSQLだけを自動的にやり直す。',
 '例外を無視し、3つ目のSQLへ進む。',
 '1つ目のルーム登録も取り消される。',
 'consultationsテーブル自体が削除される。'])
story.append(Spacer(1,17))
story+=question(4,'この計算結果はいくつになる？','''price_per_person = (
    budget_total + member_count - 1
) // member_count''','budget_totalが4501、member_countが3の場合、結果とその理由として正しいものはどれですか？\n※ Pythonの // は、整数同士の場合、割り算の結果を切り下げます。',[
 '1500。4501 // 3だけを計算するため。',
 '1500.33。小数点以下をそのまま残すため。',
 '1502。割り算をしたあとに必ず1を足すため。',
 '4503。割り算は実行されないため。',
 '1501。先に人数−1を足すことで、正の整数の割り算を切り上げられるため。'])
story+=[PageBreak(),P('問題編｜取得と再表示','title')]
story+=question(5,'roomがnullの間、何が表示される？','''const [room, setRoom] = useState<Room | null>(null);

useEffect(() => {
  getRoom(roomId).then(setRoom);
}, [roomId]);

return (
  !room
    ? <p>ルームを読み込んでいます…</p>
    : <h1>{room.title}</h1>
);''','APIからの取得が成功する場合、表示はどのように変わりますか？',[
 '最初に読み込み中の文言が表示され、取得後にルーム名が表示される。',
 '最初からDB内のルーム名が表示され、通信は行われない。',
 'roomは一度nullになったら変更できないため、読み込み中のままになる。',
 'getRoomが呼ばれると、新しいルームがDBに登録される。',
 'setRoomは画面の値を変えず、取得結果をファイルに保存する。'])
story+=[Spacer(1,22),P('解答記入欄','h')]
t=Table([[P(f'第{i}問','small') for i in range(1,6)],[P('回答：　　　','body') for _ in range(5)]],colWidths=[101]*5)
t.setStyle(TableStyle([('BOX',(0,0),(-1,-1),.6,LINE),('INNERGRID',(0,0),(-1,-1),.4,LINE),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#f4efe9')),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
story += [t,Spacer(1,16),P('考えた理由・復習メモ','h'),P('________________________________________________________________\n\n________________________________________________________________\n\n________________________________________________________________','small')]
story+=[PageBreak(),P('解答と解説','title'),P('正解：第1問 B ／ 第2問 C ／ 第3問 D ／ 第4問 E ／ 第5問 A','subtitle')]
answers=[
 ('第1問　B｜入力値を画面の状態として覚える','setTitleが入力された文字を受け取り、Reactの状態であるtitleを更新します。その状態が表示に反映されます。useStateだけではDBに保存されません。'),
 ('第2問　C｜returnで、その関数の処理を終える','reasonに文字列が入っているとifの中へ進みます。setErrorで表示用のエラーを設定し、returnで関数の処理を終えるため、後ろのcreateRoomは実行されません。'),
 ('第3問　D｜関連する保存をまとめて取り消す','2つ目のSQLで例外が起きると、transaction()の例外処理でrollback()を実行します。1つ目の登録も取り消されます。テーブルそのものを削除する処理ではありません。'),
 ('第4問　E｜正の整数の割り算を切り上げる','(4501 + 3 - 1) // 3 = 4503 // 3 = 1501です。予算と人数は1以上の整数に制限しています。人数−1を先に足すことで、割り切れない場合の端数を切り上げられます。'),
 ('第5問　A｜取得後に状態を更新し、表示を切り替える','最初はroomがnullなので、読み込み中の文言を表示します。getRoomの取得が成功すると、then(setRoom)が結果をsetRoomに渡します。roomが更新され、ルーム名の表示へ切り替わります。'),
]
for title,body in answers:story.extend([P(title,'h'),P(body)])
story.extend([Spacer(1,8),P('第5問の処理の流れ','h'),C('''room = null
  ↓
「ルームを読み込んでいます…」を表示
  ↓
getRoom(roomId)でAPIから情報を取得
  ↓
setRoom(取得した情報)で画面の状態を更新
  ↓
room.title（ルーム名）を表示'''),P('覚えるポイント：getRoomは「取得」、setRoomは「画面の状態の更新」。setRoomはファイル保存やDB保存を行いません。','body')])
doc=SimpleDocTemplate(str(OUT),pagesize=A4,rightMargin=45,leftMargin=45,topMargin=49,bottomMargin=49,title='Giftia コード理解チェック - 問題と解答',author='Giftia 学習資料')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
r=PdfReader(OUT)
assert len(r.pages)==4, f'Unexpected page count: {len(r.pages)}'
texts=[p.extract_text() for p in r.pages]
for i in range(1,6):assert f'第{i}問' in ''.join(texts)
assert '解答と解説' in texts[3]
assert '解答と解説' not in ''.join(texts[:3])
print(str(OUT));print('Pages:',len(r.pages));print('Questions and answers: OK')

