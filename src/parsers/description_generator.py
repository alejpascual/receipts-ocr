"""Context-aware description generation for receipts."""

import logging
from typing import Optional, Dict, Any
from .base import BaseParser, ParseResult, ReceiptContext

logger = logging.getLogger(__name__)


class DescriptionGenerator(BaseParser):
    """Generates concise business descriptions based on category and context."""
    
    def __init__(self):
        super().__init__()
        
        # High-priority specific patterns (override category)
        self.priority_patterns = {
            'chatgpt': ['chatgpt', 'openai', 'gpt-4', 'gpt-3'],
            'rakuten_mobile': ['rakuten', '楽天', 'mobile', 'モバイル'],
        }
        
        # Transportation patterns
        self.transport_patterns = {
            'taxi': ['タクシー', 'taxi'],
            'train': ['suica', 'pasmo', '電車', '地下鉄', '駅', '◇利用日', '利用金額', '入金額'],
            'bus': ['バス'],
            'parking': ['駐車', 'parking'],  
            'fuel': ['ガソリン', '燃料'],
            'toll': ['高速', '料金', 'toll'],
        }
        
        # Food/restaurant patterns
        self.food_patterns = {
            'client_meeting': ['居酒屋', 'レストラン', '鍋', '火鍋', '食堂'],
            'coffee': ['スターバックス', 'ドトール', 'コーヒー', '珈琲', 'カフェ'],
        }
        
        # Other service patterns
        self.service_patterns = {
            'internet': ['wi-fi', 'wifi', 'インターネット', '通信'],
            'phone': ['電話', 'phone', 'tel'],
            'office_supplies': ['文具', 'ペン', 'ノート', '用紙'],
            'equipment': ['pc', 'パソコン', 'プリンタ', 'printer'],
            'electricity': ['電力', '電気'],
            'gas': ['ガス'],
            'water': ['水道'],
        }
        
        # Category-specific description mappings
        self.category_mappings = {
            'travel': self._get_travel_description,
            'entertainment': self._get_entertainment_description, 
            'communications (phone, internet, postage)': self._get_communications_description,
            'meetings': lambda text: 'client meeting',
            'Office supplies': lambda text: 'office supplies',
            'Equipment': self._get_equipment_description,
            'Utilities': self._get_utilities_description,
            'Professional fees': lambda text: 'professional services',
            'outsourced fees': lambda text: 'consulting fees',
            'Rent': lambda text: 'office rent',
            'Advertising': lambda text: 'advertising expense',
            'Memberships': lambda text: 'membership fees',
            'Education': self._get_education_description,
            'Medical': self._get_medical_description,
            'Software and Services': self._get_software_description,
            'Other': lambda text: 'business expense',
        }
    
    def parse(self, context: ReceiptContext) -> Optional[ParseResult]:
        """
        This method is not used directly. Use generate_description instead.
        """
        return None
    
    def generate_description(self, text: str, vendor: Optional[str] = None, 
                           amount: Optional[int] = None, category: str = None) -> str:
        """
        Generate concise business description based on category and context.
        
        Args:
            text: Raw OCR text
            vendor: Extracted vendor name (optional)
            amount: Extracted amount (optional)
            category: Pre-classified category
            
        Returns:
            Concise description string
        """
        text_lower = text.lower()
        
        # HIGHEST PRIORITY: Specific pattern matching (overrides category)
        for desc, patterns in self.priority_patterns.items():
            if any(pattern in text_lower for pattern in patterns):
                return self._format_description(desc)
        
        # If we have a category, use it as primary guide
        if category and category in self.category_mappings:
            desc_func = self.category_mappings[category]
            if callable(desc_func):
                description = desc_func(text_lower)
                if description:
                    return description
        
        # Fallback pattern matching by service type
        for desc, patterns in {**self.transport_patterns, **self.food_patterns, **self.service_patterns}.items():
            if any(pattern in text_lower for pattern in patterns):
                return self._format_description(desc)
        
        # Meeting context detection
        if any(keyword in text_lower for keyword in ['会議', '打合せ', 'ミーティング', '商談']):
            return 'business meeting'
        
        # Default fallback
        return 'business expense'
    
    def _format_description(self, desc: str) -> str:
        """Format description with consistent naming."""
        formatting_map = {
            'chatgpt': 'ChatGPT',
            'rakuten_mobile': 'Rakuten Mobile',
        }
        return formatting_map.get(desc, desc.replace('_', ' '))
    
    def _get_travel_description(self, text_lower: str) -> str:
        """Get specific travel description based on context."""
        for desc, patterns in self.transport_patterns.items():
            if any(pattern in text_lower for pattern in patterns):
                return self._format_description(desc)
        
        # Additional travel patterns
        if any(kw in text_lower for kw in ['ホテル', 'hotel', '宿泊']):
            return 'hotel'
        elif any(kw in text_lower for kw in ['居酒屋', 'レストラン', '鍋', '食堂']):
            return 'business meal (out of town)'
        
        return 'travel expense'
    
    def _get_entertainment_description(self, text_lower: str) -> str:
        """Get specific entertainment description based on context."""
        # Check for meeting context
        meeting_indicators = ['会議', '打合せ', 'ミーティング', '商談']
        has_meeting_context = any(ind in text_lower for ind in meeting_indicators)
        
        if any(kw in text_lower for kw in ['居酒屋']):
            return 'client meeting' if has_meeting_context else 'business dinner'
        elif any(kw in text_lower for kw in ['レストラン', '鍋', '食堂']):
            return 'client meeting' if has_meeting_context else 'business meal'
        elif any(kw in text_lower for kw in ['スターバックス', 'ドトール']):
            return 'coffee meeting' if has_meeting_context else 'coffee'
        elif any(kw in text_lower for kw in ['コーヒー', '珈琲', 'カフェ']):
            return 'coffee'
        elif any(kw in text_lower for kw in ['映画']):
            return 'movie'
        elif any(kw in text_lower for kw in ['カラオケ']):
            return 'karaoke'
        
        return 'client entertainment'
    
    def _get_communications_description(self, text_lower: str) -> str:
        """Get specific communications description."""
        if any(kw in text_lower for kw in ['rakuten mobile', '楽天モバイル']):
            return 'rakuten mobile'
        elif any(kw in text_lower for kw in ['インターネット', 'wi-fi', 'wifi']):
            return 'internet service'
        elif any(kw in text_lower for kw in ['電話', 'phone']):
            return 'phone bill'
        
        return 'communications'
    
    def _get_utilities_description(self, text_lower: str) -> str:
        """Get specific utilities description."""
        if any(kw in text_lower for kw in ['電力', '電気']):
            return 'electricity bill'
        elif any(kw in text_lower for kw in ['ガス']):
            return 'gas bill'
        elif any(kw in text_lower for kw in ['水道']):
            return 'water bill'
        
        return 'utility bill'
    
    def _get_equipment_description(self, text_lower: str) -> str:
        """Get specific equipment description."""
        equipment_map = {
            'slimblade': 'Slimblade trackball',
            'kensington': 'Kensington device', 
            'trackball': 'trackball',
            'mouse': 'mouse',
            'keyboard': 'keyboard',
            'monitor': 'monitor',
            'webcam': 'webcam',
            'desk': 'desk',
            'chair': 'office chair',
            'printer': 'printer',
            'scanner': 'scanner',
            'headphone': 'headphones',
            'speaker': 'speakers'
        }
        
        for keyword, description in equipment_map.items():
            if keyword in text_lower:
                return description
        
        return 'office equipment'
    
    def _get_education_description(self, text_lower: str) -> str:
        """Get specific education description."""
        languages = ['アラビア語', '英語', '中国語', 'フランス語', 'スペイン語', 'ドイツ語', '韓国語']
        if any(lang in text_lower for lang in languages):
            return 'language learning'
        
        bookstores = ['有隣堂', '紀伊國屋', 'tsutaya']
        if any(store in text_lower for store in bookstores):
            return 'books'
        
        if any(kw in text_lower for kw in ['教科書', '参考書', '辞書', '辞典']):
            return 'reference materials'
        elif any(kw in text_lower for kw in ['研修', 'セミナー', '講座']):
            return 'training'
        elif any(kw in text_lower for kw in ['資格', '試験', '検定']):
            return 'certification'
        
        return 'education'
    
    def _get_medical_description(self, text_lower: str) -> str:
        """Get specific medical description."""
        if any(kw in text_lower for kw in ['クリニック', 'clinic', '病院', '医院']):
            return 'medical expense'
        elif any(kw in text_lower for kw in ['歯科', '歯医者']):
            return 'dental expense'
        elif any(kw in text_lower for kw in ['薬局', 'ドラッグストア', '処方箋']):
            return 'pharmacy'
        elif any(kw in text_lower for kw in ['健康診断', '人間ドック']):
            return 'health checkup'
        elif any(kw in text_lower for kw in ['予防接種', 'ワクチン']):
            return 'vaccination'
        
        return 'medical expense'
    
    def _get_software_description(self, text_lower: str) -> str:
        """Get specific software/service description."""
        services = {
            'chatgpt': 'ChatGPT',
            'openai': 'ChatGPT',
            'gpt-4': 'ChatGPT', 
            'gpt-3': 'ChatGPT',
            'github': 'GitHub',
            'slack': 'Slack',
            'zoom': 'Zoom',
            'dropbox': 'Dropbox',
            'microsoft': 'Microsoft services',
            'adobe': 'Adobe services',
            'google': 'Google services',
            'apple': 'Apple services',
            'railway': 'Railway hosting',
            'vercel': 'Vercel hosting',
            'heroku': 'Heroku hosting',
            'aws': 'AWS services',
            'setapp': 'Setapp'
        }
        
        for keyword, description in services.items():
            if keyword in text_lower:
                return description
        
        return 'software services'