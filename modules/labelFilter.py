import re

class LabelFiller(object):
    rules = {}
    def __init__(self, rules):
        self.rules = rules
        pass
    
    # Async method accepts string, itarates all rules and return all labels with founded value or None
    # for label with type = bool method will search value in input string and returns true/false if founded
    # for label with type str and with filled regexp method will match input string with regexp and return founded value or None
    async def labelFilter(self, string, labels: dict):
        #labels = {}
        for rule in self.rules:
            bingo = False
            result = None
            isSkipRule = False
            isDropRule = False
            if 'name' not in rule: continue
            
            isFilled = False if labels.get(rule.get('name',''),None) in (False,'', None) else True
            # Check if label has be updated, use rules and current label value
            
            if 'rules' in rule and isFilled == True:
                for r in rule.get('rules',[]):
                    if r.get('type','') == 'firstEntrance':
                        isSkipRule = True
                    if 'dropAfter' in r:
                        isDropRule = True
            
            # dropAfter field contains regexp value for matching drop line
            # if match - set None to value and go to next rule
            if isDropRule:
                if re.search(r.get('dropAfter',''), string):
                    labels[rule['name']] = None
                    continue
                    
            # Skip rule if label is filled
            if isSkipRule and isFilled:
                continue                
            
            # Search value
            #If rule has regexp - search match by regexp, if no -search 'value' in string
            if 'regexp' in rule:
                if 'LR1121' in string:
                    pass
                match = re.search(rule['regexp'], string)            
                if match:
                    bingo = True
                    result = match.group(1) if len(match.groups()) > 0 else match.group(0)
            elif 'value' in rule:
                if rule['value'] in string:
                    bingo = True
                    result =string
            else:
                #Skip rule
                continue
            
            # Fill labels by values
            # Bool rule return True/False
            if rule.get('type','') == 'bool':
                if bingo:
                    labels[rule['name']] = True
                #else:
                #    labels[rule['name']] = False
            # str rule return founded value
            elif rule.get('type','') == 'str':
                if bingo:
                    labels[rule['name']] = result
                #else:
                #    labels[rule['name']] = None
        withValues =[]
        for l in labels:
            if labels.get(l,'') not in (False,'', None):
                withValues.append(l)
        
        return  withValues, labels
    

        
    #async method get keywords from string, get string and regexp with matching groups and return list of founded values. 
    async def getKeywords(self, string, regexp):
        keywords = []
        keywords = re.findall(regexp, string)
        return keywords
        
    