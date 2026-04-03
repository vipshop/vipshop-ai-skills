#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
唯品会商品详情查询工具
支持查询商品主信息、商品辅助信息并进行分析总结
"""

import sys
import json
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, List, Any, Optional


def load_login_tokens() -> Optional[Dict[str, Any]]:
    """
    加载登录态
    
    Returns:
        登录态字典，包含cookies等信息；如果未登录返回None
    """
    token_file = Path.home() / ".vipshop-user-login" / "tokens.json"
    
    if not token_file.exists():
        return None
    
    try:
        with open(token_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 检查是否是新格式（包含cookies字段）
        if data and isinstance(data, dict) and 'cookies' in data:
            return data
        return None
    except Exception as e:
        sys.stderr.write(f"加载登录态失败: {e}\n")
        return None


def make_request(url: str, cookies: Optional[Dict[str, str]] = None, post_data: Optional[Dict[str, Any]] = None, post_json: bool = False) -> Dict[str, Any]:
    """
    发起 HTTP GET 或 POST 请求并返回 JSON 响应

    Args:
        url: 请求URL
        cookies: 可选的cookie字典
        post_data: 可选的POST数据字典，如果提供则使用POST请求
        post_json: 如果为True，使用JSON格式发送POST数据

    Returns:
        JSON响应数据
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://www.vip.com/',
            'Origin': 'https://www.vip.com'
        }

        # 如果有POST数据，使用POST请求
        if post_data:
            if post_json:
                headers['Content-Type'] = 'application/json; charset=UTF-8'
                encoded_data = json.dumps(post_data, ensure_ascii=False).encode('utf-8')
            else:
                headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
                encoded_data = urllib.parse.urlencode(post_data).encode('utf-8')
            req = urllib.request.Request(url, data=encoded_data, headers=headers, method='POST')
        else:
            req = urllib.request.Request(url, headers=headers)

        # 如果有cookies，构建Cookie头
        if cookies:
            cookie_str = '; '.join([f'{k}={v}' for k, v in cookies.items()])
            req.add_header('Cookie', cookie_str)

        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read().decode('utf-8')
            return json.loads(data)
    except Exception as e:
        return {"error": str(e)}


def get_product_main_info(product_id: str) -> Dict[str, Any]:
    """
    获取商品主信息（使用商品详情主信息接口）

    Args:
        product_id: 商品ID

    Returns:
        商品主信息
    """
    url = "https://mapi-pc.vip.com/vips-mobile/rest/shopping/skill/detail/main/v6"

    # 加载登录态
    login_data = load_login_tokens()
    cookies = {}
    mars_cid = ''  # 使用登录态中的 mars_cid

    if login_data:
        login_cookies = login_data.get('cookies', {})
        if 'PASSPORT_ACCESS_TOKEN' in login_cookies:
            cookies['PASSPORT_ACCESS_TOKEN'] = login_cookies['PASSPORT_ACCESS_TOKEN']
        if 'mars_cid' in login_cookies:
            mars_cid = login_cookies['mars_cid']

    # POST请求参数
    post_data = {
        'app_name': 'shop_pc',
        'app_version': '4.0',
        'warehouse': 'VIP_NH',
        'fdc_area_id': '944101105114',
        'client': 'pc',
        'mobile_platform': '1',
        'province_id': '104104',
        'api_key': 'dafe77e7486f46eca2e17a256d3ce6b5',
        'mars_cid': mars_cid,
        'is_default_area': '0',
        'productId': product_id,
        'standby_id': 'nature',
        'scene': 'detail',
        'opts': 'priceView:13;quotaInfo:1;restrictTips:1;panelView:3;foreShowActive:1;invisible:1;floatingView:1;announcement:1;svipView:2;showSingleColor:1;svipPriceMode:1;promotionTips:6;foldTips:3;formula:2;extraDetailImages:1;shortVideo:1;countryFlagStyle:1;saleServiceList:1;storeInfo:3;brandCountry:1;freightTips:3;priceBannerView:1;bannerTagsView:1;buyMoreFormula:1;mergeGiftTips:0;kf:1;priceIcon:1;tuv:3;promotionTags:7;mergeGiftTips:3;topDetailImage:2;deliveryInfo:1;installServiceList:1;efficiencyImages:1;relatedProdSpu:1'
    }

    # 使用POST方式发起请求，使用form-urlencoded格式
    response = make_request(url, cookies if cookies else None, post_data=post_data, post_json=False)

    if "error" in response:
        return {"error": f"商品主信息请求失败: {response['error']}"}

    if response.get("code") != 1:
        # 检查是否是token过期
        if response.get("code") == 11000:
            return {"error": "token_expired", "message": response.get("msg", "token expired")}
        return {"error": f"商品主信息接口错误，code={response.get('code')}, msg={response.get('msg', '')}"}

    return response.get("data", {})


def get_product_more_info(product_id: str, main_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    获取商品辅助信息（使用商品详情辅助信息接口）

    Args:
        product_id: 商品ID
        main_info: 商品主信息（用于获取moreCtx）

    Returns:
        商品辅助信息
    """
    return get_product_more_info_v2(product_id, main_info)


def get_product_more_info_v2(product_id: str, main_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    获取商品辅助信息 v2（使用商品详情辅助信息接口）

    Args:
        product_id: 商品ID
        main_info: 商品主信息（用于获取moreCtx）

    Returns:
        商品辅助信息
    """
    base_url = "https://mapi-pc.vip.com/vips-mobile/rest/shopping/skill/detail/more/v2"

    # 加载登录态
    login_data = load_login_tokens()
    cookies = {}
    mars_cid = ''  # 使用登录态中的 mars_cid

    if login_data:
        login_cookies = login_data.get('cookies', {})
        if 'PASSPORT_ACCESS_TOKEN' in login_cookies:
            cookies['PASSPORT_ACCESS_TOKEN'] = login_cookies['PASSPORT_ACCESS_TOKEN']
        if 'mars_cid' in login_cookies:
            mars_cid = login_cookies['mars_cid']

    # 从主信息中获取moreCtx
    more_ctx = main_info.get("moreCtx", "")

    # 构建opts参数
    opts = "sizeTable:1;sizeRecommend:1;reputation:2"

    # POST请求参数
    post_data = {
        'app_name': 'shop_pc',
        'app_version': '4.0',
        'warehouse': 'VIP_NH',
        'fdc_area_id': '944101105114',
        'client': 'pc',
        'mobile_platform': '1',
        'province_id': '104104',
        'api_key': 'dafe77e7486f46eca2e17a256d3ce6b5',
        'mars_cid': mars_cid,
        'wap_consumer': 'c',
        'is_default_area': '0',
        'scene': 'detail',
        'productId': product_id,
        'opts': opts,
        'moreCtx': more_ctx
    }

    # 使用POST方式发起请求，使用form-urlencoded格式
    response = make_request(base_url, cookies if cookies else None, post_data=post_data, post_json=False)

    if "error" in response:
        return {"error": f"商品辅助信息请求失败: {response['error']}"}

    if response.get("code") != 1:
        # 检查是否是token过期
        if response.get("code") == 11000:
            return {"error": "token_expired", "message": response.get("msg", "token expired")}
        return {"error": f"商品辅助信息接口错误，code={response.get('code')}"}

    return response.get("data", {})


def analyze_product_info(main_info: Dict[str, Any], more_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    分析总结商品信息

    Args:
        main_info: 商品主信息（商品详情）
        more_info: 商品辅助信息（价格、属性、标签等）

    Returns:
        分析总结后的商品信息
    """
    result = {}

    # 从主信息中提取数据（商品详情）
    if main_info and isinstance(main_info, dict):
        # 商品详情主信息接口返回的数据结构
        base = main_info.get("base", {})
        brand_store_info = main_info.get("brandStoreInfo", {})
        product_id = main_info.get("productId", "")

        # 1. 商品图片：取前3张，取 previewImages.imageUrl 字段
        image_list = []
        images = main_info.get("images", {})
        if images and isinstance(images, dict):
            groups = images.get("groups", {})
            if groups and isinstance(groups, dict):
                # 遍历所有分组，获取预览图
                for key in groups:
                    preview_images = groups[key].get("previewImages", [])
                    if preview_images and isinstance(preview_images, list):
                        for img in preview_images[:3]:  # 取前3张
                            if isinstance(img, dict):
                                img_url = img.get("imageUrl", "")
                                if img_url:
                                    image_list.append(img_url)
                                if len(image_list) >= 3:
                                    break
                    if len(image_list) >= 3:
                        break
        if image_list:
            result["商品图片"] = image_list

        # 2. 商品信息：品牌名 拼接 商品名称，例如：品牌名 ｜ 商品名称
        brand_name = brand_store_info.get("brandStoreName", "") if brand_store_info else ""
        product_title = base.get("title", "")
        if product_title:
            if brand_name:
                result["商品信息"] = f"{brand_name}｜{product_title}"
            else:
                result["商品信息"] = product_title

        # 3. 价格信息：优先从 sellPriceTags 提取，如果没有则从 salePrice 提取
        products = main_info.get("products", {})
        if products and isinstance(products, dict):
            for pid, product_data in products.items():
                if isinstance(product_data, dict):
                    price_view = product_data.get("priceView", {})
                    if price_view and isinstance(price_view, dict):
                        price_info = {}
                        
                        # 优先从 sellPriceTags 提取价格信息（注意：这是数组）
                        sell_price_tags = price_view.get("sellPriceTags", [])
                        if sell_price_tags and isinstance(sell_price_tags, list):
                            # sellPriceTags 结构：[{"price": "xxx", "priceTips": "超V特卖价"}, ...]
                            for tag_data in sell_price_tags:
                                if isinstance(tag_data, dict):
                                    price_value = tag_data.get("price", "")
                                    price_text = tag_data.get("priceTips", "")
                                    if price_value and price_text:
                                        price_info[price_text] = price_value
                        
                        # 从 salePrice 补充折扣信息（sellPriceTags 不包含折扣）
                        sale_price = price_view.get("salePrice", {})
                        if sale_price and isinstance(sale_price, dict):
                            if sale_price.get("saleDiscount"):
                                price_info["折扣"] = sale_price.get("saleDiscount", "")
                        
                        # 如果 sellPriceTags 没有数据，从 salePrice 提取全部价格信息
                        if len(price_info) <= 1:  # 只有折扣或为空
                            if sale_price and isinstance(sale_price, dict):
                                if sale_price.get("salePrice"):
                                    price_info["特卖价"] = sale_price.get("salePrice", "")
                                if sale_price.get("saleMarketPrice"):
                                    price_info["市场价"] = sale_price.get("saleMarketPrice", "")

                        if price_info:
                            result["价格信息"] = price_info
                    break

        # 4. 价格计算公式：formula.detail 下的 t 字段拼接起来
        formula = main_info.get("formula", {})
        if formula and isinstance(formula, dict):
            detail = formula.get("detail", {})
            if detail and isinstance(detail, dict):
                t_values = detail.get("t", [])
                if t_values and isinstance(t_values, list):
                    formula_text = "".join([str(t) for t in t_values if t])
                    if formula_text:
                        result["价格计算公式"] = formula_text

        # 5. 优惠信息：取 foldTips、svipFoldTips 两个字段信息
        discount_info = []

        # foldTips
        fold_tips = main_info.get("foldTips", {})
        if fold_tips and isinstance(fold_tips, dict):
            for key, tip_data in fold_tips.items():
                if isinstance(tip_data, dict):
                    discount_info.append({
                        "类型": tip_data.get("type", ""),
                        "提示语": tip_data.get("tips", "")
                    })

        # svipFoldTips
        svip_fold_tips = main_info.get("svipFoldTips", {})
        if svip_fold_tips and isinstance(svip_fold_tips, dict):
            for key, tip_data in svip_fold_tips.items():
                if isinstance(tip_data, dict):
                    discount_info.append({
                        "类型": tip_data.get("type", ""),
                        "提示语": tip_data.get("tips", "")
                    })

        if discount_info:
            result["优惠信息"] = discount_info

        # 6. 优惠券信息：取 foldCoupons 字段
        fold_coupons = main_info.get("foldCoupons", {})
        if fold_coupons and isinstance(fold_coupons, dict):
            coupons_list = []
            for coupon_key, coupon_data in fold_coupons.items():
                if isinstance(coupon_data, dict):
                    coupon_info = {
                        "优惠券描述": coupon_data.get("text", ""),
                        "使用门槛": coupon_data.get("subTips", ""),
                        "购买价": coupon_data.get("buy", ""),
                        "优惠金额": coupon_data.get("fav", ""),
                        "使用时间": coupon_data.get("couponTips", "")
                    }
                    coupons_list.append(coupon_info)
            if coupons_list:
                result["优惠券信息"] = coupons_list

        # 7. 服务标签：取 afterSaleServices.title 字段
        after_sale_services = main_info.get("afterSaleServices", [])
        if after_sale_services and isinstance(after_sale_services, list):
            tags_list = []
            for service in after_sale_services:
                if isinstance(service, dict) and service.get("title"):
                    tags_list.append(service.get("title", ""))
            if tags_list:
                result["服务标签"] = tags_list

        # 8. 正品信息：取 commitment4 字段
        commitment4 = main_info.get("commitment4", {})
        if commitment4 and isinstance(commitment4, dict):
            # 提取正品保障相关信息
            authenticity_info = []
            for key, value in commitment4.items():
                if isinstance(value, dict):
                    info_text = value.get("text", "")
                    if info_text:
                        authenticity_info.append(info_text)
                elif isinstance(value, str):
                    if value and not value.startswith("http") and value != "defaultItem":
                        authenticity_info.append(value)
            if authenticity_info:
                result["正品信息"] = authenticity_info
        else:
            # 如果没有commitment4，尝试从其他字段提取正品信息
            # 例如：products中的commitment相关字段
            products = main_info.get("products", {})
            if products and isinstance(products, dict):
                for pid, product_data in products.items():
                    if isinstance(product_data, dict):
                        # 查找各种承诺字段
                        for field_name in ["commitment", "commitment1", "commitment2", "commitment3", "commitment4", "commitments"]:
                            commitment_data = product_data.get(field_name)
                            if commitment_data:
                                authenticity_info = []
                                if isinstance(commitment_data, dict):
                                    for key, value in commitment_data.items():
                                        if isinstance(value, dict):
                                            info_text = value.get("text", "")
                                            if info_text:
                                                authenticity_info.append(info_text)
                                        elif isinstance(value, str):
                                            if value and not value.startswith("http") and value != "defaultItem":
                                                authenticity_info.append(value)
                                elif isinstance(commitment_data, str):
                                    if commitment_data and not commitment_data.startswith("http") and commitment_data != "defaultItem":
                                        authenticity_info.append(commitment_data)
                                if authenticity_info:
                                    result["正品信息"] = authenticity_info
                                    break
                        break

        # 9. 链接：拼接PC链接 https://detail.vip.com/detail-${base.brandId}-${productId}.html
        brand_id = base.get("brandId", "")
        if brand_id and product_id:
            result["链接"] = f"https://detail.vip.com/detail-{brand_id}-{product_id}.html"

    # 8. 精华评论：取前两条（从辅助信息中提取）
    if more_info and isinstance(more_info, dict) and not more_info.get("error"):
        reputation = more_info.get("reputation", {})
        if reputation and isinstance(reputation, dict):
            product_reputation = reputation.get("productReputation", {})
            if product_reputation and isinstance(product_reputation, dict):
                reputation_list = product_reputation.get("productReputationList", [])
                if reputation_list and isinstance(reputation_list, list) and len(reputation_list) > 0:
                    # 取前两条评价的 content 字段
                    reviews = []
                    for i in range(min(2, len(reputation_list))):
                        item = reputation_list[i]
                        if isinstance(item, dict):
                            reputation_content = item.get("reputation", {})
                            if reputation_content and isinstance(reputation_content, dict):
                                content = reputation_content.get("content", "")
                                if content:
                                    reviews.append(content)
                    if reviews:
                        result["精华评论"] = reviews

    return result


def get_product_detail(product_id: str) -> Dict[str, Any]:
    """
    主函数：获取唯品会商品详情

    Args:
        product_id: 商品ID

    Returns:
        JSON格式的商品详情
    """
    if not product_id:
        return {"error": "请提供商品ID"}

    # 检查登录态
    login_data = load_login_tokens()
    if login_data is None:
        return {
            "error": "login_required",
            "message": "需要登录唯品会账户",
            "action": "请先登录唯品会账户后再查询商品详情"
        }

    # 步骤1: 获取商品主信息（商品详情）
    main_result = get_product_main_info(product_id)

    if "error" in main_result:
        # 检查是否是token过期
        if main_result.get("error") == "token_expired":
            return {"error": "token_expired", "message": "登录已过期，请重新登录"}
        return {"error": f"获取商品主信息失败：{main_result['error']}"}

    # 步骤2: 获取商品辅助信息（价格、属性、标签等）
    more_result = get_product_more_info(product_id, main_result)

    if "error" in more_result:
        # 如果辅助信息获取失败，使用空字典
        print(f"警告：获取商品辅助信息失败：{more_result['error']}", file=sys.stderr)
        more_result = {}

    # 步骤3: 分析总结商品信息
    analysis_result = analyze_product_info(main_result, more_result)

    # 步骤4: 组装完整结果（不包含原始数据）
    result = {
        "商品ID": product_id,
        "分析总结": analysis_result
    }

    return result


def main():
    """命令行入口 - 输出JSON格式数据"""
    if len(sys.argv) < 2:
        sys.stderr.write("用法: python detail.py <商品ID>\n")
        sys.stderr.write("示例: python detail.py 6921775422265919647\n")
        sys.exit(1)

    product_id = sys.argv[1]
    result = get_product_detail(product_id)

    # 输出JSON格式数据，确保中文正常显示
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
