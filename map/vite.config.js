import { defineConfig } from 'vite';
import { viteSingleFile } from 'vite-plugin-singlefile';

export default defineConfig({
  base: './',
  plugins: [
    viteSingleFile(),
    {
      name: 'inject-single-file-template',
      apply: 'build',
      generateBundle(options, bundle) {
        if (bundle['index.html']) {
          const html = bundle['index.html'].source;
          // Вшиваем шаблон в глобальную переменную
          bundle['index.html'].source = html.replace(
            '</body>',
            `<script>window.__SINGLE_FILE_TEMPLATE__ = ${JSON.stringify(html)};</script></body>`
          );
        }
      }
    }
  ]
});