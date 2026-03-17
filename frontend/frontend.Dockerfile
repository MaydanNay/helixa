FROM node:20-slim

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy application code
COPY . .

# Expose Vite port
EXPOSE 5173

# Run in dev mode for high-fidelity updates
CMD ["npm", "run", "dev", "--", "--host"]
