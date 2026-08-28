// next.config.js의 webpack asset/source 규칙으로 .md를 문자열로 import 합니다.
declare module "*.md" {
  const content: string;
  export default content;
}
