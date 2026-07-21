require('dotenv').config();
const express = require('express');
const session = require('express-session');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 5000;

// Middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, 'public')));
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

app.use(session({
  secret: process.env.SESSION_SECRET || 'secure-system-key-2024',
  resave: false,
  saveUninitialized: false,
}));

const { createClient } = require('@supabase/supabase-js');

// Supabase Connection
const supabaseUrl = process.env.SUPABASE_URL || 'YOUR_SUPABASE_URL';
const supabaseKey = process.env.SUPABASE_KEY || 'YOUR_SUPABASE_ANON_KEY';
const supabase = createClient(supabaseUrl, supabaseKey);

// Make supabase available to routers via req.app.locals
app.locals.supabase = supabase;

// Routes
// app.use('/', require('./routes/auth'));
// app.use('/ea', require('./routes/ea'));
// app.use('/aef', require('./routes/aef'));

app.get('/', (req, res) => {
  res.redirect('/home'); 
});

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
