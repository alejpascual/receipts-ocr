"""Category classification using rules and heuristics."""

import yaml
import logging
import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)


class CategoryClassifier:
    """Classify receipts into predefined categories using rules and fuzzy matching."""
    
    def __init__(self, rules_path: Path):
        """
        Initialize classifier with category rules.
        
        Args:
            rules_path: Path to categories.yml file
        """
        self.rules_path = rules_path
        self.categories = {}
        self.load_rules()
    
    def load_rules(self):
        """Load category rules from YAML file."""
        try:
            with open(self.rules_path, 'r', encoding='utf-8') as f:
                self.categories = yaml.safe_load(f)
            logger.info(f"Loaded {len(self.categories)} category rules")
        except Exception as e:
            logger.error(f"Failed to load category rules: {e}")
            raise
    
    def classify(self, vendor: Optional[str], description: str, text: str) -> Tuple[str, float]:
        """
        Classify a receipt into a category.
        
        Args:
            vendor: Extracted vendor name
            description: Generated description
            text: Full OCR text
            
        Returns:
            Tuple of (category, confidence_score)
        """
        all_text = f"{vendor or ''} {description} {text}".lower()
        
        category_scores = {}
        
        # Score each category based on keyword matches
        for category, rules in self.categories.items():
            if category == 'Other':
                continue
                
            score = self._calculate_category_score(all_text, rules.get('any', []))
            if score > 0:
                category_scores[category] = score
        
        # Apply special heuristics
        heuristic_scores = self._apply_heuristics(vendor, description, text)
        for category, score in heuristic_scores.items():
            category_scores[category] = category_scores.get(category, 0) + score
        
        if not category_scores:
            logger.info("No category match found, defaulting to 'Other'")
            return "Other", 0.1
        
        # Get best category
        best_category = max(category_scores.items(), key=lambda x: x[1])
        
        # Check for conflicts (multiple high-scoring categories) - be more lenient
        high_scores = [cat for cat, score in category_scores.items() 
                      if score >= best_category[1] * 0.9]  # Increased threshold to 90%
        
        if len(high_scores) > 1:
            # Only conflict if the scores are very close (within 1 point)
            best_score = best_category[1]
            close_scores = [cat for cat, score in category_scores.items() 
                           if abs(score - best_score) <= 1.0]
            if len(close_scores) > 1:
                logger.warning(f"Category conflict detected: {close_scores}")
                return "Other", 0.3  # Low confidence due to conflict
        
        # Normalize confidence to 0-1 range
        confidence = min(best_category[1] / 10.0, 1.0)
        
        logger.info(f"Classified as '{best_category[0]}' with confidence {confidence:.2f}")
        return best_category[0], confidence
    
    def _calculate_category_score(self, text: str, keywords: List[str]) -> float:
        """Calculate score for a category based on keyword matches."""
        score = 0.0
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            
            # Exact match gets highest score
            if keyword_lower in text:
                score += 5.0
                continue
            
            # Fuzzy match for partial matches
            words = text.split()
            for word in words:
                similarity = fuzz.ratio(keyword_lower, word)
                if similarity >= 80:  # 80% similarity threshold
                    score += similarity / 100.0 * 3.0  # Max 3 points for fuzzy match
        
        return score
    
    def _apply_heuristics(self, vendor: Optional[str], description: str, text: str) -> Dict[str, float]:
        """Apply specific heuristics for common patterns."""
        scores = {}
        text_lower = text.lower()
        vendor_lower = (vendor or '').lower()
        desc_lower = description.lower()  # For potential future use
        
        # Transportation heuristics (but be careful about JR in building addresses)
        transport_indicators = ['地下鉄', 'タクシー', '高速', 'suica', 'pasmo', '新幹線', 'バス', '電車']
        if any(indicator in text_lower for indicator in transport_indicators):
            scores['travel'] = scores.get('travel', 0) + 3.0
        
        # Handle JR specifically - only boost travel if it's actual transport, not building address
        if 'jr' in text_lower:
            if any(transport_word in text_lower for transport_word in ['乗車', '切符', '運賃', '電車代', '駅']):
                scores['travel'] = scores.get('travel', 0) + 3.0
            elif 'ビル' in text and ('店' in text or '真巴石火鍋' in text):
                # JR building with store/restaurant - definitely not transport
                scores['travel'] = scores.get('travel', 0) - 15.0  # Very strong penalty to override rule-based score
                logger.info(f"JR building with restaurant detected, very strongly penalizing travel")
            elif 'ビル' in text:
                # JR building generally - likely not transport  
                scores['travel'] = scores.get('travel', 0) - 5.0
        
        # Communications heuristics - but be careful not to trigger on restaurant contact info
        comm_indicators = ['ntt', 'kddi', 'ソフトバンク', 'wi-fi', 'インターネット', '電話', '通信']
        if any(indicator in text_lower for indicator in comm_indicators):
            # Check if this is actually a restaurant with contact info, not a telecom business
            restaurant_context_indicators = ['料理', 'レストラン', '居酒屋', '食堂', 'カフェ', '喫茶', 'rice', 'curry', 'ライス', 'カレー', '店']
            if any(rest_indicator in text_lower for rest_indicator in restaurant_context_indicators):
                # This is a restaurant with contact info - reduce communications score
                scores['communications (phone, internet, postage)'] = scores.get('communications (phone, internet, postage)', 0) + 1.0  # Much lower score
            else:
                scores['communications (phone, internet, postage)'] = scores.get('communications (phone, internet, postage)', 0) + 3.0
        
        # IKEA classification - categorize based on actual items (check both vendor and text)
        is_ikea = (vendor_lower and any(indicator in vendor_lower for indicator in ['ikea', 'イケア'])) or \
                  any(indicator in text_lower for indicator in ['ikea', 'イケア', 'ikea渋谷', 'ikea shibuya'])
        
        if is_ikea:
            # IKEA food items and restaurant indicators
            ikea_food_indicators = [
                'プラントボール', 'plant ball', 'ミートボール', 'meatball',
                'フード', 'food', 'レストラン', 'restaurant', 'カフェ', 'cafe',
                'ホットドッグ', 'hot dog', 'ソフトクリーム', 'soft cream',
                'フィッシュ&チップス', 'fish&chips', 'fish & chips', 'フィッシュアンドチップス'
            ]
            
            # IKEA office/furniture items
            ikea_office_indicators = [
                '靴r', '靴R', '靴ラック', 'shoe rack', 'grejig', 'グレイグ',
                'デスク', 'desk', 'チェア', 'chair', '収納', 'storage',
                'ファイル', 'file', 'ボックス', 'box', 'シェルフ', 'shelf'
            ]
            
            # Check categories in order of specificity
            if any(food_item in text_lower for food_item in ikea_food_indicators):
                scores['entertainment'] = scores.get('entertainment', 0) + 10.0
                logger.info("IKEA food/restaurant detected - strongly boosting entertainment")
            elif any(office_item in text_lower for office_item in ikea_office_indicators):
                scores['Office supplies'] = scores.get('Office supplies', 0) + 10.0
                logger.info("IKEA office/furniture item detected - strongly boosting Office supplies")
            # For remaining small purchases at IKEA, likely food (under ¥1200)
            elif any(int(amount) <= 1200 for amount in re.findall(r'¥?\s*(\d{3,4})\s*¥?', text) if amount.isdigit()):
                scores['entertainment'] = scores.get('entertainment', 0) + 6.0
                logger.info("Small IKEA purchase detected - likely food, boosting entertainment")
        
        # Food/Entertainment heuristics
        if any(indicator in vendor_lower for indicator in ['スターバックス', 'ドトール', '珈琲', 'コーヒー']):
            # Check if it's a business meeting vs personal consumption
            if any(biz in text_lower for biz in ['会議', '打合せ', 'ミーティング', '商談']):
                scores['meetings'] = scores.get('meetings', 0) + 4.0
            else:
                scores['entertainment'] = scores.get('entertainment', 0) + 2.0
        
        # Restaurant/Bar heuristics - restaurants default to entertainment, light refreshments to meetings
        restaurant_indicators = ['居酒屋', 'レストラン', '食事', '飲食', '鍋', '火鍋', '店', 'お食事代', '料理', 'rice', 'curry', 'ライス', 'カレー', 'gaprao', 'マヤ', 'ネパール', 'インド', 'bagel', 'cafe', 'カフェ', 'ベーグル',
                                # Enhanced food-related characters and terms that indicate restaurants
                                '牛', '肉', '焼肉', '焼き鳥', '鳥', '豚', '魚', '海鮮', '寿司', '刺身', '天ぷら', 
                                '定食', '弁当', '丼', '麺', 'ラーメン', 'うどん', 'そば', '串焼']
        if any(indicator in text_lower for indicator in restaurant_indicators):
            # Light refreshments/bento in meeting context → meetings
            if any(light_indicator in text_lower for light_indicator in ['弁当', 'ベント', 'サンドイッチ', 'おにぎり', 'パン', 'ドリンク', '飲み物', 'コーヒー', 'お茶']):
                if any(meeting_indicator in text_lower for meeting_indicator in ['会議', '打合せ', 'ミーティング', '商談', '会議室']):
                    scores['meetings'] = scores.get('meetings', 0) + 5.0  # Light refreshments in meetings
                else:
                    scores['entertainment'] = scores.get('entertainment', 0) + 3.0  # Light food without meeting context
            # Strong restaurant indicators default to entertainment
            elif any(strong_indicator in text for strong_indicator in ['真巴石火鍋', 'お食事代として', '火鍋', '鍋', '居酒屋', 'レストラン']):
                scores['entertainment'] = scores.get('entertainment', 0) + 6.0  # Clear restaurant → entertainment
            # Additional strong restaurant/food indicators
            elif any(food_indicator in text_lower for food_indicator in ['料理', 'rice', 'curry', 'ライス', 'カレー', 'gaprao', 'マヤ', 'ネパール', 'インド', 'タイ', 'thai', 'bagel', 'cafe', 'カフェ', 'ベーグル', '牛', '肉', '焼肉', '焼き鳥', '鳥', '豚', '魚', '海鮮', '寿司', '刺身', '天ぷら', '定食', '弁当', '丼', '麺', 'ラーメン', 'うどん', 'そば', '串焼']):
                scores['entertainment'] = scores.get('entertainment', 0) + 8.0  # Very clear food establishment → entertainment
            # Evening meals or alcohol usually entertainment
            elif any(indicator in text_lower for indicator in ['夜', 'ビール', '酒', 'アルコール']):
                scores['entertainment'] = scores.get('entertainment', 0) + 3.0
            else:
                scores['entertainment'] = scores.get('entertainment', 0) + 4.0  # Default restaurants to entertainment
        
        # Office supplies from major retailers
        office_retailers = ['amazon', 'アマゾン', 'ヨドバシ', 'ビックカメラ']
        if any(retailer in vendor_lower for retailer in office_retailers):
            if any(item in text_lower for item in ['文具', 'ペン', 'ノート', 'コピー', '用紙']):
                scores['Office supplies'] = scores.get('Office supplies', 0) + 3.0
            elif any(item in text_lower for item in ['pc', 'パソコン', 'ディスプレイ', 'プリンタ']):
                scores['Equipment'] = scores.get('Equipment', 0) + 3.0
        
        # Equipment keywords
        equipment_indicators = ['pc', 'パソコン', 'ノートパソコン', 'mac', 'ディスプレイ', 'プリンタ', 'カメラ']
        if any(indicator in text_lower for indicator in equipment_indicators):
            scores['Equipment'] = scores.get('Equipment', 0) + 4.0
        
        # Utilities pattern matching
        utility_companies = ['東京電力', '東京ガス', '関西電力', '中部電力']
        if any(company in text_lower for company in utility_companies):
            scores['Utilities'] = scores.get('Utilities', 0) + 5.0
        
        # Professional services
        if any(indicator in text_lower for indicator in ['弁護士', '税理士', '会計士', 'コンサル']):
            scores['Professional fees'] = scores.get('Professional fees', 0) + 4.0
        
        # Outsourcing keywords
        if any(indicator in text_lower for indicator in ['外注', '委託', '請負', '業務委託']):
            scores['outsourced fees'] = scores.get('outsourced fees', 0) + 4.0
        
        # Rent/Real estate
        if any(indicator in text_lower for indicator in ['家賃', '賃料', 'オフィス', 'テナント']):
            scores['Rent'] = scores.get('Rent', 0) + 5.0
        
        # Advertising
        ad_indicators = ['google ads', 'facebook', 'meta', '広告', 'リスティング']
        if any(indicator in text_lower for indicator in ad_indicators):
            scores['Advertising'] = scores.get('Advertising', 0) + 4.0
        
        # Education/Books heuristics - bookstores and educational materials
        if any(bookstore in text_lower for bookstore in ['有隣堂', '紀伊國屋', 'tsutaya', 'ブックストア', 'bookstore']):
            # Check if it's actually books/educational content
            education_indicators = [
                '本', '書籍', '教科書', '参考書', '語学', '英語', '中国語', 'アラビア語', 'フランス語', 
                'スペイン語', 'ドイツ語', '韓国語', '学習', '勉強', '教育', '辞書', '辞典',
                '本の在庫', 'isbn', '復習', '基本', '入門', '初級', '中級', '上級'
            ]
            if any(edu_indicator in text_lower for edu_indicator in education_indicators):
                scores['Education'] = scores.get('Education', 0) + 10.0  # Very strong boost for education
                # Reduce entertainment score since bookstores might be miscategorized as entertainment
                scores['entertainment'] = max(0, scores.get('entertainment', 0) - 5.0)
                logger.info("Bookstore with educational content detected - strongly boosting Education")
            else:
                # General bookstore purchase - still likely educational
                scores['Education'] = scores.get('Education', 0) + 6.0
                logger.info("Bookstore purchase detected - boosting Education")
        
        # Language learning materials detection
        language_indicators = ['アラビア語', '英語', '中国語', 'フランス語', 'スペイン語', 'ドイツ語', '韓国語', '語学', '復習', '基本']
        if any(lang in text_lower for lang in language_indicators):
            scores['Education'] = scores.get('Education', 0) + 8.0  # Strong boost for language learning
            logger.info("Language learning material detected - boosting Education")
        
        # Medical/Healthcare heuristics
        medical_indicators = ['クリニック', 'clinic', '病院', '医院', '診療所', '歯科', '歯医者']
        medical_context_indicators = ['保険管理', '保険点数', '診察', '治療', '医療費', '薬局', 'ドラッグストア']
        
        if any(indicator in text_lower for indicator in medical_indicators):
            scores['Medical'] = scores.get('Medical', 0) + 10.0  # Very strong boost for medical facilities
            logger.info("Medical facility detected - strongly boosting Medical")
        elif any(indicator in text_lower for indicator in medical_context_indicators):
            scores['Medical'] = scores.get('Medical', 0) + 8.0  # Strong boost for medical context
            logger.info("Medical context detected - boosting Medical")
        # Special case: "点数" alone could mean purchase items, only boost Medical if in medical context
        elif '点数' in text_lower and any(medical_word in text_lower for medical_word in ['保険', '医療', '診察', '治療', 'クリニック', '病院']):
            scores['Medical'] = scores.get('Medical', 0) + 6.0  # Moderate boost for medical points
            logger.info("Medical point system context detected - boosting Medical")
        
        # Special detection for Japanese medical point system
        if '点' in text and any(medical_word in text_lower for medical_word in ['保険', '医療', '診察', '治療']):
            scores['Medical'] = scores.get('Medical', 0) + 12.0  # Very strong boost for medical points
            logger.info("Japanese medical point system detected - very strongly boosting Medical")
        
        # Membership fees - but check if it's promotional text on restaurant receipts
        if any(indicator in text_lower for indicator in ['会費', '年会費', 'メンバーシップ', '入会金']):
            # Check if this is actually a restaurant with promotional membership text
            restaurant_transaction_indicators = [
                'pizza', 'pasta', 'ボンゴレ', 'ビアンコ', 'テーブル', '人数:', '担当者:', 
                'pos:', '点数', '小計', '合計', '内消費税', 'お預り', 'おつり'
            ]
            restaurant_name_indicators = ['papa milano', 'ダイナック', 'pizza&pasta']
            
            has_restaurant_transaction = any(indicator in text_lower for indicator in restaurant_transaction_indicators)
            has_restaurant_name = any(indicator in text_lower for indicator in restaurant_name_indicators)
            
            if has_restaurant_transaction or has_restaurant_name:
                # This is likely promotional text on a restaurant receipt
                scores['entertainment'] = scores.get('entertainment', 0) + 12.0  # Very strong boost for entertainment
                scores['Memberships'] = scores.get('Memberships', 0) + 0.5  # Very weak membership signal
                logger.info("Restaurant receipt with promotional membership text detected - strongly boosting entertainment")
            else:
                # Likely actual membership fee
                scores['Memberships'] = scores.get('Memberships', 0) + 4.0
        
        # Geographic detection - outside Tokyo = travel
        # Tokyo indicators - Enhanced with English ward names and variations
        tokyo_indicators = ['東京都', '東京', 'Tokyo', 'tokyo', 'TOKYO', '渋谷', '新宿', '品川', '池袋', '上野', '銀座', '六本木', '恵比寿', 
                           '表参道', '原宿', '秋葉原', '浅草', '丸の内', '有楽町', '新橋', '目黒', '中野', 
                           '吉祥寺', '立川', '八王子', '町田', '府中', '調布', '三鷹', '武蔵野市', '杉並区', 
                           '世田谷区', '大田区', '江東区', '墨田区', '台東区', '荒川区', '足立区', '葛飾区', 
                           '江戸川区', '練馬区', '板橋区', '北区', '豊島区', '文京区', '千代田区', '中央区', 
                           '港区', '目黒区', '品川区', 
                           # English ward names and variations
                           'Minato-ku', 'Shibuya', 'Shinjuku', 'Azabu', 'Shibuya-ku', 'Shinjuku-ku', 'Minato-ku',
                           'Chiyoda-ku', 'Chuo-ku', 'Bunkyo-ku', 'Taito-ku', 'Sumida-ku', 'Koto-ku', 'Shinagawa-ku',
                           'Meguro-ku', 'Ota-ku', 'Setagaya-ku', 'Suginami-ku', 'Nakano-ku', 'Toshima-ku',
                           'Kita-ku', 'Itabashi-ku', 'Nerima-ku', 'Adachi-ku', 'Katsushika-ku', 'Edogawa-ku', 'Arakawa-ku',
                           # Common Tokyo locations in English
                           'Jingumae', 'Roppongi', 'Ginza', 'Akasaka', 'Ebisu', 'Harajuku', 'Omotesando']
        
        # Non-Tokyo locations (major cities and prefectures)
        # Note: Removed "京都" as it conflicts with "東京都" (Tokyo Metropolis)
        non_tokyo_indicators = ['大阪', '神戸', '名古屋', '福岡', '札幌', '仙台', '広島', '岡山', 
                               '熊本', '鹿児島', '沖縄', '北海道', '青森', '岩手', '宮城', '秋田', '山形', 
                               '福島', '茨城', '栃木', '群馬', '埼玉', '千葉', '神奈川', '新潟', '富山', 
                               '石川', '福井', '山梨', '長野', '岐阜', '静岡', '愛知', '三重', '滋賀', 
                               '京都府', '大阪府', '兵庫', '奈良', '和歌山', '鳥取', '島根', '岡山県', 
                               '広島県', '山口', '徳島', '香川', '愛媛', '高知', '福岡県', '佐賀', '長崎', 
                               '熊本県', '大分', '宮崎', '鹿児島県', '沖縄県']
        
        # Check Tokyo indicators FIRST to avoid conflicts with non-Tokyo patterns
        tokyo_found = any(location in text for location in tokyo_indicators)
        non_tokyo_found = any(location in text for location in non_tokyo_indicators)
        
        # Strong Tokyo indicators that should override OCR errors
        strong_tokyo_indicators = ['Tokyo', 'tokyo', 'TOKYO', 'Minato-ku', 'Shibuya', 'Shibuya-ku', 'Azabu', 
                                  '東京都', '港区', '渋谷区', 'Jingumae', ', Japan', 'Japan']
        strong_tokyo_found = any(indicator in text for indicator in strong_tokyo_indicators)
        
        # Special handling for office rental/tax invoices - should always be Rent category
        if any(office_indicator in text for office_indicator in ['TAX INVOICE', 'Office', 'Kitchen Amenities', 'BOKSEN', 'Account number:', 'Invoice number:']):
            scores['Rent'] = scores.get('Rent', 0) + 25.0  # Very strong boost for Rent
            scores['entertainment'] = max(0, scores.get('entertainment', 0) - 20.0)  # Strong penalty for entertainment
            scores['travel'] = max(0, scores.get('travel', 0) - 20.0)  # Strong penalty for travel
            scores['Other'] = max(0, scores.get('Other', 0) - 10.0)  # Penalty for Other
            logger.info(f"Office rental/tax invoice detected, strongly boosting Rent category and penalizing entertainment")
        # Special handling for Legal Affairs Bureau - should always be Other category
        # But exclude receipts from stores (they just have stamp tax info)
        elif (any(legal_indicator in text_lower for legal_indicator in ['法務局', '登記', '登記簿']) or 
              ('印紙' in text_lower and not any(store_indicator in text_lower for store_indicator in ['ikea', 'イケア', '店舗', 'pos', '取引', '購入', '商品', 'レシート', '領収証']))):
            scores['Other'] = scores.get('Other', 0) + 20.0  # Very strong boost for Other
            scores['travel'] = max(0, scores.get('travel', 0) - 25.0)  # Very strong penalty for travel
            scores['Professional fees'] = max(0, scores.get('Professional fees', 0) - 10.0)  # Penalty for professional fees
            scores['Office supplies'] = max(0, scores.get('Office supplies', 0) - 10.0)  # Penalty for office supplies
            logger.info(f"Legal Affairs Bureau detected, strongly boosting Other category and penalizing travel")
        elif tokyo_found:
            # Check if this is a restaurant/food establishment in Tokyo
            if any(food_indicator in text_lower for food_indicator in ['居酒屋', 'レストラン', '飲食', '鍋', '火鍋', '食堂', 'コーヒー', '珈琲', 'カフェ', 'スターバックス', 'ドトール', 'indian', 'restaurant']):
                # Tokyo restaurants should be entertainment, not travel
                penalty_strength = 20.0 if strong_tokyo_found else 15.0  # Extra strong if we have very clear Tokyo indicators
                scores['entertainment'] = scores.get('entertainment', 0) + 12.0  # Very strong boost
                scores['travel'] = max(0, scores.get('travel', 0) - penalty_strength)  # Very strong penalty
                logger.info(f"Tokyo restaurant/food detected (strong={strong_tokyo_found}), strongly boosting entertainment and penalizing travel")
            # For non-food Tokyo locations, reduce travel unless it's actual transport
            elif not any(transport in text_lower for transport in ['駅', '乗車', '切符', '運賃', '電車代', 'suica', 'pasmo']):
                penalty_strength = 15.0 if strong_tokyo_found else 10.0
                scores['travel'] = max(0, scores.get('travel', 0) - penalty_strength)  # Strong reduction
                logger.info(f"Tokyo non-transport detected (strong={strong_tokyo_found}), strongly reducing travel category")
        # Check for non-Tokyo locations - but only if we don't have strong Tokyo indicators
        elif non_tokyo_found and not strong_tokyo_found:
            # Very strong travel indicator for non-Tokyo locations - overrides everything
            scores['travel'] = scores.get('travel', 0) + 15.0  # Very high priority
            # Reduce competing categories when outside Tokyo
            for other_cat in ['entertainment', 'meetings']:
                if other_cat in scores:
                    scores[other_cat] = max(0, scores[other_cat] - 5.0)
            logger.info(f"Non-Tokyo location detected (no strong Tokyo indicators), strongly boosting travel category")
        
        return scores
    
    def get_category_suggestions(self, text: str, top_n: int = 3) -> List[Tuple[str, float]]:
        """
        Get top N category suggestions for review purposes.
        
        Args:
            text: Full text to analyze
            top_n: Number of suggestions to return
            
        Returns:
            List of (category, score) tuples sorted by score
        """
        category_scores = {}
        text_lower = text.lower()
        
        for category, rules in self.categories.items():
            if category == 'Other':
                continue
            score = self._calculate_category_score(text_lower, rules.get('any', []))
            if score > 0:
                category_scores[category] = score
        
        # Sort by score and return top N
        sorted_categories = sorted(category_scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_categories[:top_n]