const express = require('express')
const {Readability} = require('@mozilla/readability')
const {JSDOM} = require('jsdom')

const app = express()
const HOST = '0.0.0.0'
const PORT = 3000

app.use(express.json({ limit: '10mb',  }));
app.use(express.urlencoded({ limit: '10mb', extended: true }));

app.get('/', (req, res) => {
    const url = req.body.url
    const html = req.body.html
    const doc = new JSDOM(html, {
        url: url
    })
  const reader = new Readability(doc.window.document)
  res.send(reader.parse());
})

app.listen(PORT, HOST)
console.log(`Running on http://${HOST}:${PORT}`)