import { PriceTrendApp } from "@/components/PriceTrendApp";

export default function HomePage() {
  return (
    <main>
      <h1>商品价格趋势</h1>
      <p className="caption">
        输入型号关键字，合并 F / R / V 全渠道已售样本，查看该商品的价格走势。
        不区分店铺；若含多种货币，按币种分别展示。
      </p>
      <PriceTrendApp />
    </main>
  );
}
