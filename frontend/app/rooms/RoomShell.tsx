// ルーム関連の画面で共通して使う、ヘッダー・本文の枠・フッターを表示する部品です。
import Link from "next/link";
import type { ReactNode } from "react";
import "./rooms.css";

type RoomShellProps = {
  children: ReactNode;
  title?: string;
};

export default function RoomShell({ children, title }: RoomShellProps) {
  // ルーム名が渡されていない作成画面では、共通の説明を表示する。
  let headerTitle = title;
  if (headerTitle === undefined) {
    headerTitle = "みんなで決める、送別ギフト";
  }

  return (
    <div className="room-app">
      {/* すべてのルーム画面で共通のヘッダー */}
      <header className="room-header">
        <div className="room-header-inner">
          <Link href="/rooms/new" className="room-logo" aria-label="Giftia ルームを作る">
            Giftia<span className="room-logo-dot">.</span>
          </Link>
          <span className="room-header-title">{headerTitle}</span>
          <nav aria-label="メインメニュー">
            <Link href="/">ギフトを探す</Link>
            <Link href="/rooms/new" className="room-nav-current">ルームを作る</Link>
          </nav>
        </div>
      </header>

      {/* 呼び出し元がRoomShellの中に書いた内容を、ここへ表示する */}
      <main className="room-main">{children}</main>

      <footer className="room-footer">
        <span>Giftia</span> 大切な人への贈りものを、みんなで。
      </footer>
    </div>
  );
}
