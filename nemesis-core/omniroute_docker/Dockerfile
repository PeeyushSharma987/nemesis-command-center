FROM node:20-alpine
RUN addgroup -S omni && adduser -S omni -G omni
RUN npm install -g omniroute@latest && npm cache clean --force
USER omni
WORKDIR /home/omni
EXPOSE 4000
CMD ["omniroute", "start", "--port", "4000", "--host", "0.0.0.0"]
