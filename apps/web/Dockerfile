FROM node:20-slim AS deps
WORKDIR /app
COPY package.json ./
RUN npm install

FROM node:20-slim AS builder
WORKDIR /app
# NEXT_PUBLIC_* vars are inlined into the client JS bundle at `next build` time —
# setting them as container `environment:` at runtime has no effect. They must be
# passed as build args (see docker-compose.yml `build.args`) and exported as ENV
# before the build step so Next.js's compiler can see them.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ARG NEXT_PUBLIC_KAKAO_JS_KEY=
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
ENV NEXT_PUBLIC_KAKAO_JS_KEY=${NEXT_PUBLIC_KAKAO_JS_KEY}
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-slim AS runner
ENV NODE_ENV=production TZ=Asia/Seoul
WORKDIR /app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
