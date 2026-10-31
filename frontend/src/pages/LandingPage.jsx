import { Link } from 'react-router-dom'
import { ArrowRight, BadgePercent, ChartColumn, FileText, Layers, Receipt, Repeat, ShieldCheck, UserRound, Users } from 'lucide-react'
import { BrandMark } from '../components/Brand'
import { useAuth } from '../context/AuthContext'
import './Landing.css'

const FEATURES = [
  { icon: Layers, title: 'Products, variants and plans', text: 'Sell software by the day, week, month or year. Add brand variants such as Odoo (+₹560) and decide per plan what can be paused, closed early or renewed.' },
  { icon: FileText, title: 'Quotations to subscriptions', text: 'Start from a template, set a validity period, and turn an accepted quote into a live subscription in one click.' },
  { icon: Receipt, title: 'Invoices that write themselves', text: 'Every billing day, invoices are created from subscriptions with taxes and totals filled in. Nothing is billed twice or skipped.' },
  { icon: BadgePercent, title: 'Taxes and discounts as rules', text: 'Admins set tax rules once. Discounts apply on their own to the next invoice and stop when they expire or run out.' },
  { icon: Repeat, title: 'Payments, matched', text: 'Record method, amount, date and a note against the right invoice, and see what is paid, outstanding and overdue at a glance.' },
  { icon: ChartColumn, title: 'Revenue you can trust', text: 'Active subscriptions, MRR, collections and overdue invoices in one place, fast even with thousands of subscriptions.' },
]

const STEPS = [
  ['01', 'Set up the catalog', 'Products, variants, plans, taxes and discounts.'],
  ['02', 'Quote the customer', 'Use a template, add lines, set how long it stays valid.'],
  ['03', 'Confirm and activate', 'Draft, Quotation, Confirmed, Active, Closed. Always visible.'],
  ['04', 'Bill automatically', 'One billing run creates every due invoice.'],
  ['05', 'Collect payments', 'Record each payment and chase what is overdue.'],
  ['06', 'Report', 'Finance sees revenue, receivables and growth live.'],
]

const ROLES = [
  { icon: ShieldCheck, name: 'Admin', text: 'Controls the whole system: products, plans, taxes, discounts, staff and every report.' },
  { icon: Users, name: 'Staff', text: 'Handles customers day to day: quotations, subscriptions, invoices and payments.' },
  { icon: UserRound, name: 'Customer', text: 'Sees their own subscriptions and invoices, pays online, and pauses, upgrades or renews themselves.' },
]

export default function LandingPage() {
  const { user } = useAuth()

  return (
    <div className="landing">
      <header className="l-nav">
        <Link to="/" className="l-brand">
          <BrandMark size={34} />
          <span>
            Brightloop <i>Billing</i>
          </span>
        </Link>
        <nav>
          <a href="#what">What it is</a>
          <a href="#features">Features</a>
          <a href="#how">How it works</a>
          <a href="#roles">Who uses it</a>
        </nav>
        <div className="l-nav-actions">
          {user ? (
            <Link to="/dashboard" className="l-btn l-btn-rose">
              Open dashboard <ArrowRight size={16} />
            </Link>
          ) : (
            <>
              <Link to="/login" className="l-btn l-btn-ghost">
                Log in
              </Link>
              <Link to="/register" className="l-btn l-btn-rose">
                Register
              </Link>
            </>
          )}
        </div>
      </header>

      <section className="l-hero">
        <div className="l-hero-copy">
          <span className="l-tag">Subscription management and recurring billing</span>
          <h1>
            Run every plan,
            <br />
            <em>invoice</em> and <strong>payment</strong>
            <br />
            in one place.
          </h1>
          <p>
            Brightloop Billing is a subscription management platform for businesses that earn every month. Set up products and plans, quote
            customers, bill automatically, collect payments and report revenue, without a spreadsheet in sight.
          </p>
          <div className="l-cta">
            <Link to={user ? '/dashboard' : '/register'} className="l-btn l-btn-rose l-btn-lg">
              {user ? 'Open dashboard' : 'Create an account'} <ArrowRight size={18} />
            </Link>
            {!user && (
              <Link to="/login" className="l-btn l-btn-outline l-btn-lg">
                Log in
              </Link>
            )}
          </div>
          <ul className="l-proof">
            <li>Role-based access</li>
            <li>Automatic invoicing</li>
            <li>Live revenue reports</li>
          </ul>
        </div>

        <div className="l-hero-art" aria-hidden="true">
          <div className="l-glow" />
          <div className="l-card l-card-main">
            <div className="l-card-top">
              <span>Monthly recurring revenue</span>
              <b>+12.4%</b>
            </div>
            <strong>₹14,24,100</strong>
            <svg viewBox="0 0 300 80" className="l-spark">
              <defs>
                <linearGradient id="lg" x1="0" x2="1">
                  <stop offset="0" stopColor="#007ba7" />
                  <stop offset="1" stopColor="#ff2d95" />
                </linearGradient>
              </defs>
              <path d="M0 62 L40 55 L80 58 L120 42 L160 46 L200 28 L240 20 L300 6" fill="none" stroke="url(#lg)" strokeWidth="3" strokeLinecap="round" />
            </svg>
            <div className="l-rows">
              <div>
                <i className="ok" /> INV-00231 <span>Paid</span>
              </div>
              <div>
                <i className="warn" /> INV-00232 <span>Due in 4 days</span>
              </div>
              <div>
                <i className="ok" /> SUB-00118 <span>Renewed</span>
              </div>
            </div>
          </div>
          <div className="l-card l-card-float l-card-a">
            <small>Active subscriptions</small>
            <strong>1,284</strong>
          </div>
          <div className="l-card l-card-float l-card-b">
            <small>Collected this month</small>
            <strong>₹9.8 L</strong>
          </div>
        </div>
      </section>

      <section id="what" className="l-section l-what">
        <div className="l-what-copy">
          <span className="l-kicker">What this website is</span>
          <h2>A billing back office for subscription businesses.</h2>
          <p>
            Many companies sell software and services on subscription but still track customers in a spreadsheet, type invoices by hand and
            match payments from bank statements. Brightloop Billing replaces all of that with one system the whole team and every customer
            can log into.
          </p>
        </div>
        <div className="l-stats">
          <div>
            <strong>5</strong>
            <span>billing frequencies, from daily to yearly</span>
          </div>
          <div>
            <strong>3</strong>
            <span>roles: admin, staff and customer</span>
          </div>
          <div>
            <strong>0</strong>
            <span>invoices typed by hand</span>
          </div>
        </div>
      </section>

      <section id="features" className="l-section">
        <span className="l-kicker">Features</span>
        <h2>Everything a billing month needs.</h2>
        <div className="l-grid">
          {FEATURES.map(({ icon: Icon, title, text }) => (
            <article key={title} className="l-feature">
              <Icon size={22} />
              <h3>{title}</h3>
              <p>{text}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="how" className="l-section">
        <span className="l-kicker">How it works</span>
        <h2>From a new customer to the month-end report.</h2>
        <ol className="l-steps">
          {STEPS.map(([n, title, text]) => (
            <li key={n}>
              <b>{n}</b>
              <h3>{title}</h3>
              <p>{text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section id="roles" className="l-section">
        <span className="l-kicker">Who uses it</span>
        <h2>The right access for everyone.</h2>
        <div className="l-roles">
          {ROLES.map(({ icon: Icon, name, text }) => (
            <article key={name}>
              <Icon size={22} />
              <h3>{name}</h3>
              <p>{text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="l-final">
        <h2>
          Ready to see your <em>recurring revenue</em> clearly?
        </h2>
        <div className="l-cta center">
          <Link to={user ? '/dashboard' : '/register'} className="l-btn l-btn-rose l-btn-lg">
            {user ? 'Open dashboard' : 'Get started'} <ArrowRight size={18} />
          </Link>
          {!user && (
            <Link to="/login" className="l-btn l-btn-outline l-btn-lg">
              Log in
            </Link>
          )}
        </div>
      </section>

      <footer className="l-footer">
        <span>© Brightloop Software. Subscription billing, made calm.</span>
      </footer>
    </div>
  )
}
