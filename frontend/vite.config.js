import { defineConfig } from 'vite';
export default defineConfig({server:{port:8080,proxy:{'/api':{target:'http://localhost:8001',changeOrigin:true},'/bills':{target:'http://localhost:8000',changeOrigin:true},'/tables':{target:'http://localhost:8000',changeOrigin:true}}}});
