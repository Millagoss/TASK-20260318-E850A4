FROM node:20-slim

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

# Expose Vite dev server port
EXPOSE 5173

# Vite as PID 1 (npm swallows signals / odd exits during compose recreate)
CMD ["./node_modules/.bin/vite", "--host", "0.0.0.0"]