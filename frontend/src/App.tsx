import { Navigate, Route, Routes } from "react-router-dom";
import { BrandProvider } from "./contexts/BrandContext";
import { AppShell } from "./components/layout/AppShell";
import { ProtectedRoute } from "./routes/ProtectedRoute";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { DashboardPage } from "./pages/DashboardPage";
import { BrandNewPage } from "./pages/BrandNewPage";
import { OnboardingPage } from "./pages/OnboardingPage";
import { SettingsPage } from "./pages/SettingsPage";
import { AdsPage } from "./pages/AdsPage";
import { AdDetailPage } from "./pages/AdDetailPage";
import { AdComparePage } from "./pages/AdComparePage";
import { ProfilePage } from "./pages/ProfilePage";
import { ABTestsPage } from "./pages/ABTestsPage";
import { ABTestDetailPage } from "./pages/ABTestDetailPage";
import { ABWizardPage } from "./pages/ABWizardPage";
import { ABRecommendationsPage } from "./pages/ABRecommendationsPage";
import { TimelinePage } from "./pages/TimelinePage";
import { BriefsPage } from "./pages/BriefsPage";
import { BriefDetailPage } from "./pages/BriefDetailPage";
import { AccountPage } from "./pages/AccountPage";

export default function App(): React.ReactElement {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        element={
          <ProtectedRoute>
            <BrandProvider>
              <AppShell />
            </BrandProvider>
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<DashboardPage />} />
        <Route path="/brands/new" element={<BrandNewPage />} />
        <Route path="/onboarding" element={<OnboardingPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/ads" element={<AdsPage />} />
        <Route path="/ads/compare" element={<AdComparePage />} />
        <Route path="/ads/:adId" element={<AdDetailPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/tests" element={<ABTestsPage />} />
        <Route path="/tests/new" element={<ABWizardPage />} />
        <Route path="/tests/recommendations" element={<ABRecommendationsPage />} />
        <Route path="/tests/:testId" element={<ABTestDetailPage />} />
        <Route path="/timeline" element={<TimelinePage />} />
        <Route path="/briefs" element={<BriefsPage />} />
        <Route path="/briefs/:jobId" element={<BriefDetailPage />} />
        <Route path="/account" element={<AccountPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
