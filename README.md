# Brightloop Billing

Subscription management and recurring billing system. Django REST API plus a React app.

## What you need

- Python 3.12 or newer
- Node.js 20 or newer
- Git

## 1. Get the code

```bash
git clone <repo-url>
cd Subscription_Management_System_
```

## 2. Start the backend (Terminal 1)

```bash
python -m venv venv
```

Turn the virtual environment on:

- Windows: `venv\Scripts\activate`
- Mac or Linux: `source venv/bin/activate`

Then:

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo
python manage.py runserver
```

- `createsuperuser` makes your own login. After it, open the Django shell and set the role to admin (see below).
- `seed_demo` adds sample customers, plans and invoices so the screens are not empty.
- The API runs at http://localhost:8000.

Make your user an admin:

```bash
python manage.py shell -c "from accounts.models import User; User.objects.filter(username='YOUR_NAME').update(role='admin')"
```

## 3. Start the frontend (Terminal 2)

```bash
cd frontend
npm install
npm run dev
```

Open the address it prints (usually http://localhost:5173).

## Logging in

- Use the admin you made above to see everything.
- Sample customers from `seed_demo` are named `demo_...`. Their password is printed when you run `seed_demo`.
- Users can also register on the Register page. They get the customer role.

## Roles

| Role | Can do |
|---|---|
| Admin | Everything: products, plans, taxes, discounts, users |
| Staff | Subscriptions, quotations, invoices, payments, reports |
| Customer | Browse plans, see own subscriptions, invoices and payments |

## Useful commands

```bash
python manage.py test            # run all tests
python manage.py run_billing     # create invoices for subscriptions that are due
```

## Notes

- Sign-up checks that the email address looks real (domain exists, and Gmail mailbox exists). To turn this off, set `VERIFY_EMAIL_EXISTS=0` before starting the backend.
- Emails (like password reset links) are printed in the backend terminal. No real mail is sent.
- Data is stored in a local `db.sqlite3` file.
- If the frontend can not reach the backend, check that the backend is running on port 8000.
