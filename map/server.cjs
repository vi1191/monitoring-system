const express = require('express');
const fs = require('fs');
const path = require('path');
const cors = require('cors');

const app = express();
app.use(cors());
app.use(express.json({ limit: '50mb' }));

app.post('/api/export', (req, res) => {
  try {
    const templatePath = path.join(__dirname, 'public', 'template.html');
    let html = fs.readFileSync(templatePath, 'utf8');

    const dataJson = JSON.stringify(req.body).replace(/</g, '\\u003c');
    const injectScript = `<script id="embedded-data" type="application/json">${dataJson}</scr` + `ipt>
<script>window.__EMBEDDED_DATA__ = JSON.parse(document.getElementById("embedded-data").textContent);</scr` + `ipt>`;
    
    html = html.replace('</body>', injectScript + '\n</body>');
    
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    res.setHeader('Content-Disposition', 'attachment; filename="karta_tehniki.html"');
    res.send(html);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.listen(3001, () => console.log('Сервер экспорта запущен на порту 3001'));