# 매뉴얼 문서

매뉴얼 **본문(Markdown)** 은 웹앱 안에서 그대로 렌더링되므로, 웹앱의 빌드 컨텍스트
(`apps/web`) 안으로 옮겼습니다. 내용을 고칠 때는 아래 파일만 수정하면 화면과 배포본이
함께 갱신됩니다.

| 문서 | 원본(Markdown) | 앱 화면 |
|---|---|---|
| 일반 임직원 사용자 매뉴얼 | [`apps/web/src/content/manuals/employee.md`](../../apps/web/src/content/manuals/employee.md) | `/manual` |
| 관리자 사용 매뉴얼 | [`apps/web/src/content/manuals/admin.md`](../../apps/web/src/content/manuals/admin.md) | `/manual/admin` (SYSTEM_ADMIN 전용) |

이 폴더의 PDF는 배포·인쇄용 사본입니다. Markdown을 고친 뒤에는 PDF도 다시 내보내
주세요. (PDF만 고치면 화면 내용과 어긋납니다.)
