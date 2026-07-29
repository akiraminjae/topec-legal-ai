import Link from "next/link";

export default function HomePage() {
  return (
    <main className="flex min-h-screen items-center justify-center">
      <div className="text-center">
        <h1 className="text-2xl font-bold text-brand-700">TOPEC Legal AI</h1>
        <p className="mt-2 text-slate-500">AI 계약·법률 검토 지원 시스템 (내부 임직원 전용)</p>
        <Link href="/login" className="mt-6 inline-block rounded bg-brand-600 px-4 py-2 text-white">
          로그인
        </Link>
      </div>
    </main>
  );
}
