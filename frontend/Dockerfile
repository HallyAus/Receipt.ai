# Frontend Dockerfile - Development
FROM node:20-slim

WORKDIR /app

# Copy package files
COPY package.json ./

# Install dependencies
RUN npm install

# Copy source
COPY . .

# Expose port
EXPOSE 3000

# Development server
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
