FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 5173

CMD ["sh", "-c", "if [ \"${FRONTEND_MODE:-production}\" = \"development\" ]; then npm run dev -- --host 0.0.0.0 --port 5173; else npm run build && npm run preview -- --host 0.0.0.0 --port 5173; fi"]
