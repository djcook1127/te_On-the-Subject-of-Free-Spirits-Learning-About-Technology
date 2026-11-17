// ルームの作成・取得をAPIに依頼し、受け取り期限の確認や日付の表示を行うプログラムです。
import calendar from "../../shared/japan-holidays.json";

// 画面とAPIが同じ祝日データを使う。公開カレンダーなので秘密情報は含まない。
export const holidays: Record<string, string> = calendar.holidays;
export const supportedYears = calendar.supported_years;
export const calendarSource = calendar.source;
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const localRoomsEnabled = process.env.NEXT_PUBLIC_LOCAL_ROOMS === "1";

// 作成するときに、画面からAPIへ送る情報。
export type RoomInput = {
  title: string;
  budget_total: number;
  member_count: number;
  deliver_by: string;
  nickname: string;
};

// 作成・取得に成功したとき、APIから画面へ返ってくる情報。
// 受け取る項目を一つずつ書き、RoomInputとの違いが分かるようにする。
export type Room = {
  room_id: number;
  title: string;
  budget_total: number;
  member_count: number;
  deliver_by: string;
  organizer_nickname: string;
  price_per_person: number;
  room_path: string;
  local_preview?: boolean;
};

export function japanToday(): string {
  // sv-SEは「年-月-日」の形式。今日の日付は日本時間で判定する。
  const formatter = new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Asia/Tokyo",
  });
  return formatter.format(new Date());
}

export function unavailableDate(day: string, today = japanToday()): string | null {
  // ① 入力が「年-月-日」の形になっているか確認する。
  const isDateFormat = /^\d{4}-\d{2}-\d{2}$/.test(day);
  if (!isDateFormat) {
    return "受け取り期限を選んでください";
  }

  // ② 2月30日のような、実在しない日付を除く。
  const date = new Date(`${day}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) {
    return "日付を確認してください";
  }
  const convertedDay = date.toISOString().slice(0, 10);
  if (convertedDay !== day) {
    return "日付を確認してください";
  }

  // ③ 祝日データがある年か、今日以降かを確認する。
  const year = date.getUTCFullYear();
  if (!supportedYears.includes(year)) {
    return "祝日データのある2026年・2027年から選んでください";
  }
  if (day < today) {
    return "今日以降を選んでください";
  }

  // ④ 祝日・土日を除く。JavaScriptでは日曜日が0、土曜日が6。
  const holidayName = holidays[day];
  if (holidayName) {
    return holidayName;
  }
  const weekday = date.getUTCDay();
  if (weekday === 0 || weekday === 6) {
    return "土日には設定できません";
  }

  // 理由がない（null）場合、この日を選択できる。
  return null;
}

export function displayDate(day: string): string {
  const formatter = new Intl.DateTimeFormat("ja-JP", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "short",
    timeZone: "Asia/Tokyo",
  });
  const date = new Date(`${day}T00:00:00+09:00`);
  return formatter.format(date);
}

async function responseRoom(response: Response): Promise<Room> {
  // ① 成功した場合は、本文をJSONとして読み取って返す。
  if (response.ok) {
    const roomData: Room = await response.json();
    return roomData;
  }

  // ② 失敗した場合は、APIが返した説明を読み取る。
  let message: string | null = null;
  try {
    const errorData = await response.json();
    if (errorData && typeof errorData.detail === "string") {
      message = errorData.detail;
    }
  } catch {
    // JSONの説明がない場合は、下の共通メッセージを使う。
  }

  if (message !== null) {
    throw new Error(message);
  }
  if (response.status === 422) {
    throw new Error("入力内容を確認してください。予算・人数は1以上、受け取り期限は今日以降の土日祝日以外にしてください。");
  }
  throw new Error("ルームを保存・取得できませんでした。時間をおいてもう一度お試しください。");
}

export async function createRoom(input: RoomInput): Promise<Room> {
  try {
    // ① 送信先と、送信用のJSON文字列を用意する。
    const url = `${API}/api/rooms`;
    const requestBody = JSON.stringify(input);

    // ② APIへ作成を依頼し、レスポンスが届くまで待つ。
    const response = await fetch(url, {
      method: "POST",
      credentials: localRoomsEnabled ? "include" : "omit",
      headers: { "Content-Type": "application/json" },
      body: requestBody,
    });

    // ③ 成功・失敗を確認し、作成したルーム情報を返す。
    const roomData = await responseRoom(response);
    return roomData;
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error("APIに接続できません。FastAPIの起動と接続先を確認してください。");
    }
    throw error;
  }
}

export async function getRoom(id: string, signal?: AbortSignal): Promise<Room> {
  try {
    // ① URLのルーム番号を、APIの取得先URLへ組み込む。
    const roomId = encodeURIComponent(id);
    const url = `${API}/api/rooms/${roomId}`;

    // ② 保存済みの情報を取得する。signalは、不要になった通信の中止用。
    const response = await fetch(url, {
      cache: "no-store",
      signal: signal,
    });

    // ③ 本文を読み取り、取得したルーム情報を返す。
    const roomData = await responseRoom(response);
    return roomData;
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error("APIに接続できません。FastAPIの起動と接続先を確認してください。");
    }
    throw error;
  }
}
