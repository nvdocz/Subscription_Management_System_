import { Navigate, Route, Routes } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import LandingPage from './pages/LandingPage'
import VerifyEmailPage from './pages/VerifyEmailPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import ForgotPasswordPage from './pages/ForgotPasswordPage'
import ResetPasswordPage from './pages/ResetPasswordPage'
import DashboardPage from './pages/DashboardPage'
import ReportsPage from './pages/ReportsPage'
import UsersPage from './pages/UsersPage'
import AddUserPage from './pages/AddUserPage'
import AccountPage from './pages/AccountPage'
import BrowsePlansPage from './pages/BrowsePlansPage'
import ProductsPage from './pages/ProductsPage'
import ProductFormPage from './pages/ProductFormPage'
import PlansPage from './pages/PlansPage'
import PlanFormPage from './pages/PlanFormPage'
import TaxRulesPage from './pages/TaxRulesPage'
import DiscountsPage from './pages/DiscountsPage'
import QuotationsPage from './pages/QuotationsPage'
import QuotationFormPage from './pages/QuotationFormPage'
import QuotationTemplatesPage from './pages/QuotationTemplatesPage'
import QuotationTemplateFormPage from './pages/QuotationTemplateFormPage'
import SubscriptionsPage from './pages/SubscriptionsPage'
import SubscriptionFormPage from './pages/SubscriptionFormPage'
import SubscriptionDetailPage from './pages/SubscriptionDetailPage'
import InvoicesPage from './pages/InvoicesPage'
import InvoiceDetailPage from './pages/InvoiceDetailPage'
import PaymentsPage from './pages/PaymentsPage'
import PaymentFormPage from './pages/PaymentFormPage'
import BillingRunPage from './pages/BillingRunPage'

const ADMIN = ['admin']
const OPERATIONS = ['admin', 'staff']

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/verify-email/:uid/:token" element={<VerifyEmailPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password/:uid/:token" element={<ResetPasswordPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          {/* every signed-in role (customers only ever receive their own records from the API) */}
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/account" element={<AccountPage />} />
          <Route path="/browse-plans" element={<BrowsePlansPage />} />
          <Route path="/quotations" element={<QuotationsPage />} />
          <Route path="/subscriptions" element={<SubscriptionsPage />} />
          <Route path="/subscriptions/:id" element={<SubscriptionDetailPage />} />
          <Route path="/invoices" element={<InvoicesPage />} />
          <Route path="/invoices/:id" element={<InvoiceDetailPage />} />
          <Route path="/payments" element={<PaymentsPage />} />

          {/* admin and internal staff */}
          <Route element={<ProtectedRoute allowedRoles={OPERATIONS} />}>
            <Route path="/reports" element={<ReportsPage />} />
            <Route path="/users" element={<UsersPage />} />
            <Route path="/users/new" element={<AddUserPage />} />
            <Route path="/subscriptions/new" element={<SubscriptionFormPage />} />
            <Route path="/subscriptions/:id/edit" element={<SubscriptionFormPage />} />
            <Route path="/quotations/new" element={<QuotationFormPage />} />
            <Route path="/quotations/:id/edit" element={<QuotationFormPage />} />
            <Route path="/quotation-templates" element={<QuotationTemplatesPage />} />
            <Route path="/quotation-templates/new" element={<QuotationTemplateFormPage />} />
            <Route path="/payments/new" element={<PaymentFormPage />} />
            <Route path="/billing-run" element={<BillingRunPage />} />
            <Route path="/tax-rules" element={<TaxRulesPage />} />
            <Route path="/discounts" element={<DiscountsPage />} />
          </Route>

          {/* admin only */}
          <Route element={<ProtectedRoute allowedRoles={ADMIN} />}>
            <Route path="/products" element={<ProductsPage />} />
            <Route path="/products/new" element={<ProductFormPage />} />
            <Route path="/products/:id/edit" element={<ProductFormPage />} />
            <Route path="/plans" element={<PlansPage />} />
            <Route path="/plans/new" element={<PlanFormPage />} />
            <Route path="/plans/:id/edit" element={<PlanFormPage />} />
          </Route>
        </Route>
      </Route>

      <Route path="/" element={<LandingPage />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}

export default App
