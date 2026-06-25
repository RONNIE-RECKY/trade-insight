import { Pricing } from "@/components/Pricing";

export default function PricingPage() {
  return (
    <div className="space-y-6">
      <div className="text-center">
        <h1 className="text-2xl font-bold text-neutral-100">Plans &amp; packages</h1>
        <p className="mt-2 text-sm text-neutral-500">
          Pick the package that fits how you trade. Upgrade or cancel anytime.
        </p>
      </div>
      <Pricing />
    </div>
  );
}
