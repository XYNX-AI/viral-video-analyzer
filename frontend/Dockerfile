FROM node:20-bookworm-slim AS build

WORKDIR /app/frontend
RUN corepack enable
RUN corepack prepare pnpm@10.29.3 --activate
RUN pnpm config set registry https://registry.npmmirror.com
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend ./
ARG NEXT_PUBLIC_API_URL=
ARG BACKEND_URL=http://backend:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV BACKEND_URL=$BACKEND_URL
RUN pnpm build

FROM node:20-bookworm-slim AS runtime
ENV NODE_ENV=production
WORKDIR /app
COPY --from=build /app/frontend/.next/standalone ./
COPY --from=build /app/frontend/.next/static ./.next/static
COPY --from=build /app/frontend/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
