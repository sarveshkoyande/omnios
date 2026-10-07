import { useState } from "react";
import { AudiencesTab } from "./AudiencesTab";
import { BrandIqTab } from "./BrandIqTab";
import { ChannelsTab } from "./ChannelsTab";
import { ComplianceTab } from "./ComplianceTab";
import { MarketTab } from "./MarketTab";
import { MessageTab } from "./MessageTab";
import { ProductTab } from "./ProductTab";
import { TABS, type PageProps, type TabId } from "./shared";

export const TAB_PAGE: Record<TabId, (p: PageProps) => React.ReactNode> = {
  brandiq: BrandIqTab, market: MarketTab, audiences: AudiencesTab, message: MessageTab,
  channels: ChannelsTab, product: ProductTab, compliance: ComplianceTab,
};

/** All seven Brand Kit tabs in one place (the Brand Compass Agent's canvas). `rev` reloads the open tab
 *  after each agent step without losing which tab is open. */
export function KitTabs({ rev = 0, ...props }: PageProps & { rev?: number }) {
  const [tab, setTab] = useState<TabId>("brandiq");
  const Page = TAB_PAGE[tab];
  return (<>
    <nav className="v3-biq-kittabs" aria-label="Brand Kit tabs">
      {TABS.map((t) => <button key={t.id} type="button" className={t.id === tab ? "active" : ""} onClick={() => setTab(t.id)}>{t.title}</button>)}
    </nav>
    <Page key={`${props.activeBrand}:${rev}`} {...props} />
  </>);
}
